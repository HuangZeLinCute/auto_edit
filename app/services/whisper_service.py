import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger("AutoEdit")
settings = get_settings()


class WhisperService:
    def __init__(self):
        self.model = None
        self.model_size = settings.whisper_model_size
        self.device = settings.whisper_device
        self.compute_type = settings.whisper_compute_type

    def _load_model(self):
        if self.model is None:
            try:
                from faster_whisper import WhisperModel

                logger.info(
                    "Loading faster-whisper model: size=%s device=%s",
                    self.model_size,
                    self.device,
                )
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                self._backend = "faster_whisper"
            except Exception as e:
                faster_whisper_error = e
                logger.warning("faster-whisper 加载失败: %s, 尝试 openai-whisper", e)
                import os

                os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
                try:
                    import whisper

                    logger.info(
                        "Loading openai-whisper model: size=%s device=cpu", self.model_size
                    )
                    self.model = whisper.load_model(self.model_size, device="cpu")
                    self._backend = "openai_whisper"
                except Exception as openai_error:
                    raise RuntimeError(
                        "Whisper 模型加载失败。请确认网络可访问模型仓库，"
                        "或提前下载模型到本机缓存；也可以在 .env 中设置 "
                        "WHISPER_MODEL_SIZE=tiny 使用最小模型。"
                        f" faster-whisper错误: {faster_whisper_error}; "
                        f"openai-whisper错误: {openai_error}"
                    ) from openai_error

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        word_timestamps: bool = True,
    ) -> dict:
        self._load_model()
        logger.info(
            "Starting transcription: %s (backend=%s)",
            audio_path,
            getattr(self, "_backend", "unknown"),
        )

        if getattr(self, "_backend", "") == "openai_whisper":
            return self._transcribe_openai(audio_path, language, word_timestamps)

        segments_iter, info = self.model.transcribe(
            audio_path,
            language=language,
            word_timestamps=word_timestamps,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        segments = []
        for idx, seg in enumerate(segments_iter):
            words = []
            if seg.words:
                for w in seg.words:
                    words.append(
                        {
                            "word": w.word.strip(),
                            "start": round(w.start, 3),
                            "end": round(w.end, 3),
                            "score": round(w.probability, 3),
                        }
                    )
            segments.append(
                {
                    "id": idx,
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text.strip(),
                    "words": words,
                }
            )

        result = {
            "language": info.language,
            "duration": round(info.duration, 3),
            "segments": segments,
        }

        logger.info(
            "Transcription done: lang=%s dur=%.1f segments=%d",
            info.language,
            info.duration,
            len(segments),
        )
        return result

    def _transcribe_openai(
        self, audio_path: str, language: Optional[str], word_timestamps: bool
    ) -> dict:
        import os

        result = self.model.transcribe(
            audio_path,
            language=language or "zh",
            word_timestamps=word_timestamps,
            verbose=False,
        )

        segments = []
        for idx, seg in enumerate(result.get("segments", [])):
            words = []
            for w in seg.get("words", []):
                words.append(
                    {
                        "word": w["word"].strip(),
                        "start": round(w["start"], 3),
                        "end": round(w["end"], 3),
                        "score": round(w.get("probability", 0), 3),
                    }
                )
            segments.append(
                {
                    "id": idx,
                    "start": round(seg["start"], 3),
                    "end": round(seg["end"], 3),
                    "text": seg["text"].strip(),
                    "words": words,
                }
            )

        total_dur = segments[-1]["end"] if segments else 0

        output = {
            "language": result.get("language", "zh"),
            "duration": round(total_dur, 3),
            "segments": segments,
        }

        logger.info(
            "Transcription done (openai): lang=%s dur=%.1f segments=%d",
            output["language"],
            output["duration"],
            len(segments),
        )
        return output

    def transcribe_with_whisperx_alignment(
        self,
        audio_path: str,
        language: str = "zh",
    ) -> dict:
        try:
            import whisperx

            device = self.device
            model = whisperx.load_model(
                self.model_size, device, compute_type=self.compute_type
            )
            audio = whisperx.load_audio(audio_path)
            result = model.transcribe(audio, language=language)

            model_a, metadata = whisperx.load_align_model(
                language_code=language, device=device
            )
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                device,
            )

            segments = []
            for idx, seg in enumerate(result["segments"]):
                words = []
                if "words" in seg:
                    for w in seg["words"]:
                        words.append(
                            {
                                "word": w.get("word", "").strip(),
                                "start": round(w.get("start", 0), 3),
                                "end": round(w.get("end", 0), 3),
                                "score": round(w.get("score", 0), 3),
                            }
                        )
                segments.append(
                    {
                        "id": idx,
                        "start": round(seg["start"], 3),
                        "end": round(seg["end"], 3),
                        "text": seg["text"].strip(),
                        "words": words,
                    }
                )

            return {
                "language": language,
                "duration": round(len(audio) / 16000, 3),
                "segments": segments,
            }
        except ImportError:
            logger.warning("whisperx not available, falling back to faster-whisper")
            return self.transcribe(audio_path, language=language)
