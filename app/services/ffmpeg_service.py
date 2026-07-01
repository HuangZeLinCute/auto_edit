import subprocess
import json
import os
import logging
from typing import Optional

logger = logging.getLogger("AutoEdit")


class FFmpegService:
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = ""):
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path or ffmpeg_path

    def _run(
        self, cmd: list[str], timeout: int = 600, cwd: str = None
    ) -> subprocess.CompletedProcess:
        logger.debug("FFmpeg: %s", " ".join(cmd))
        result = subprocess.run(
            cmd, capture_output=True, timeout=timeout, errors="replace", cwd=cwd
        )
        stderr_text = (
            (result.stderr or b"").decode(errors="replace")
            if isinstance(result.stderr, bytes)
            else (result.stderr or "")
        )
        if result.returncode != 0:
            stderr_lower = stderr_text.lower()
            if (
                "error" in stderr_lower
                or "cannot" in stderr_lower
                or "invalid" in stderr_lower
            ):
                lines = stderr_text.strip().split("\n")
                error_lines = [
                    l
                    for l in lines
                    if any(kw in l.lower() for kw in ["error", "cannot", "invalid"])
                    and "configuration" not in l.lower()
                    and "copyright" not in l.lower()
                    and "built with" not in l.lower()
                    and "ffmpeg version" not in l.lower()
                ]
                error_text = (
                    "\n".join(error_lines[:10]) if error_lines else stderr_text[:300]
                )
                logger.error("FFmpeg error: %s", error_text)
                raise RuntimeError(f"FFmpeg error: {error_text}")
            elif result.stdout and not stderr_text:
                raise RuntimeError(f"FFmpeg error: exit code {result.returncode}")
            else:
                logger.warning(
                    "FFmpeg exit=%d stderr=%s", result.returncode, stderr_text[:200]
                )
                raise RuntimeError(
                    f"FFmpeg exit={result.returncode}: {stderr_text[:300]}"
                )
        return result

    def extract_audio(
        self,
        input_path: str,
        output_path: str,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                input_path,
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                str(sample_rate),
                "-ac",
                str(channels),
                output_path,
            ]
        )
        return output_path

    def _ffprobe_run(
        self, cmd: list[str], timeout: int = 30
    ) -> subprocess.CompletedProcess:
        if self.ffprobe and self.ffprobe != self.ffmpeg:
            return self._run(cmd, timeout)
        probe_cmd = [self.ffmpeg, "-hide_banner", "-i"]
        for i, c in enumerate(cmd):
            if c == self.ffprobe:
                continue
            if c in (
                "-v",
                "-show_entries",
                "-show_format",
                "-show_streams",
                "-print_format",
                "-of",
            ):
                continue
            if c == "quiet":
                continue
            if c.startswith("default="):
                probe_cmd.extend(
                    ["-i", c.split("=", 1)[1].split(",")[0] if "=" in c else c]
                )
                return subprocess.run(
                    probe_cmd, capture_output=True, text=True, timeout=timeout
                )
        return self._run(cmd, timeout)

    def get_duration(self, input_path: str) -> float:
        try:
            cmd = [
                self.ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-i",
                input_path,
                "-f",
                "null",
                "-",
            ]
            result = subprocess.run(
                cmd, capture_output=True, timeout=60, errors="replace"
            )
            stderr = (
                (result.stderr or b"").decode(errors="replace")
                if isinstance(result.stderr, bytes)
                else (result.stderr or "")
            )
            for line in reversed(stderr.splitlines()):
                if "time=" in line:
                    time_str = line.split("time=")[1].split(" ")[0]
                    parts = time_str.split(":")
                    if len(parts) == 3:
                        return (
                            int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                        )
                    return float(time_str)
        except Exception:
            pass

        try:
            cmd = [
                self.ffprobe,
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                input_path,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, errors="replace"
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass

        info = self.get_info(input_path)
        dur = info.get("duration", 0)
        if dur > 0:
            return dur
        raise RuntimeError(f"Cannot determine duration of {input_path}")

    def get_info(self, input_path: str) -> dict:
        cmd = [self.ffmpeg, "-hide_banner", "-i", input_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
            errors="replace",
        )
        stderr_text = (
            (result.stderr or "").decode(errors="replace")
            if isinstance(result.stderr, bytes)
            else (result.stderr or "")
        )
        info: dict = {"raw_output": stderr_text, "duration": 0.0}
        for line in stderr_text.splitlines():
            if "Duration:" in line:
                dur_str = line.split("Duration:")[1].split(",")[0].strip()
                parts = dur_str.split(":")
                if len(parts) == 3:
                    info["duration"] = float(
                        int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                    )
        return info

    def cut_video(
        self, input_path: str, output_path: str, start: float, end: float
    ) -> str:
        duration = end - start
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                input_path,
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{duration:.3f}",
                "-vf",
                "setpts=PTS-STARTPTS",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-threads",
                "1",
                "-refs",
                "1",
                "-crf",
                "28",
                "-c:a",
                "aac",
                "-avoid_negative_ts",
                "make_zero",
                output_path,
            ]
        )
        return output_path

    def cut_audio(
        self, input_path: str, output_path: str, start: float, end: float
    ) -> str:
        duration = end - start
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                input_path,
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{duration:.3f}",
                "-c:a",
                "pcm_s16le",
                output_path,
            ]
        )
        return output_path

    def concat_audio(self, input_files: list[str], output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        list_file = output_path + ".list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for fp in input_files:
                f.write(f"file '{fp}'\n")
        try:
            self._run(
                [
                    self.ffmpeg,
                    "-y",
                    "-fflags",
                    "+genpts",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    list_file,
                    "-c:a",
                    "pcm_s16le",
                    output_path,
                ]
            )
        finally:
            if os.path.exists(list_file):
                os.remove(list_file)
        return output_path

    def image_to_video(
        self,
        image_path: str,
        output_path: str,
        duration: float = 5.0,
        motion: str = "slow_zoom_in",
        fps: int = 30,
        resolution: str = "1080x1920",
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        total_frames = int(duration * fps)
        w, h = resolution.split("x")
        w2, h2 = int(w) + 200, int(h) + 300

        motion_filters = {
            "static": f"scale={resolution}",
            "slow_zoom_in": f"scale={w2}:{h2},zoompan=z='min(zoom+0.001,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={resolution}:fps={fps}",
            "slow_zoom_out": f"scale={w2}:{h2},zoompan=z='if(eq(on,1),1.3,max(zoom-0.001,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={resolution}:fps={fps}",
            "pan_left": f"scale={w2}:{h},zoompan=z='1.0':x='max(iw/2-(iw/zoom/2)-on*0.5,0)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={resolution}:fps={fps}",
            "pan_right": f"scale={w2}:{h},zoompan=z='1.0':x='min(iw/2-(iw/zoom/2)+on*0.5,iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={resolution}:fps={fps}",
            "ken_burns": f"scale={w2}:{h2},zoompan=z='min(zoom+0.0008,1.2)':x='iw/2-(iw/zoom/2)+on*0.3':y='ih/2-(ih/zoom/2)':d={total_frames}:s={resolution}:fps={fps}",
        }
        vf = motion_filters.get(motion, motion_filters["slow_zoom_in"])
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-loop",
                "1",
                "-i",
                image_path,
                "-t",
                f"{duration:.2f}",
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                output_path,
            ]
        )
        return output_path

    def concat_videos(self, input_files: list[str], output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        list_file = output_path + ".list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for fp in input_files:
                f.write(f"file '{fp}'\n")
        try:
            self._run(
                [
                    self.ffmpeg,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    list_file,
                    "-vf",
                    "setpts=PTS-STARTPTS",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-pix_fmt",
                    "yuv420p",
                    "-an",
                    output_path,
                ]
            )
        finally:
            if os.path.exists(list_file):
                os.remove(list_file)
        return output_path

    def mux_audio_video(
        self, video_path: str, audio_path: str, output_path: str
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                video_path,
                "-i",
                audio_path,
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                output_path,
            ]
        )
        return output_path

    def burn_subtitles(
        self, video_path: str, subtitle_path: str, output_path: str
    ) -> str:
        import shutil

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        sub_dir = os.path.dirname(subtitle_path)
        sub_name = os.path.basename(subtitle_path)
        if subtitle_path != sub_name:
            tmp_sub = os.path.join(
                os.path.dirname(output_path), os.path.basename(subtitle_path)
            )
            if not os.path.exists(tmp_sub) or os.path.getmtime(
                subtitle_path
            ) > os.path.getmtime(tmp_sub):
                shutil.copy2(subtitle_path, tmp_sub)
            sub_name = os.path.basename(tmp_sub)

        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                video_path,
                "-vf",
                f"ass={sub_name}",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-threads",
                "1",
                "-refs",
                "1",
                "-crf",
                "28",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                output_path,
            ],
            cwd=os.path.dirname(output_path),
        )
        return output_path

    def mix_audio(
        self,
        voice_path: str,
        bgm_path: Optional[str],
        output_path: str,
        bgm_volume_db: float = -24,
        fade_in: float = 1.0,
        fade_out: float = 2.0,
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if not bgm_path:
            import shutil

            shutil.copy2(voice_path, output_path)
            return output_path

        voice_dur = self.get_duration(voice_path)
        fade_out_start = max(0, voice_dur - fade_out)
        filter_complex = (
            f"[1:a]volume={bgm_volume_db}dB,"
            f"afade=t=in:st=0:d={fade_in},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_out},"
            f"atrim=duration={voice_dur:.3f}[bgm];"
            f"[0:a]volume=2.0[voice];"
            f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=3"
        )
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                voice_path,
                "-i",
                bgm_path,
                "-filter_complex",
                filter_complex,
                "-c:a",
                "pcm_s16le",
                output_path,
            ]
        )
        return output_path

    def add_sfx(
        self,
        audio_path: str,
        sfx_path: str,
        output_path: str,
        position: float,
        volume_db: float = -10,
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        delay_ms = int(position * 1000)

        audio_dur = self.get_duration(audio_path)

        sfx_dur = self.get_duration(sfx_path)
        if position + sfx_dur > audio_dur + 0.05:
            logger.debug(
                "sfx at %.2fs extends beyond audio (%.2fs), clamping",
                position,
                audio_dur,
            )
            delay_ms = int(max(0, audio_dur - sfx_dur - 0.02) * 1000)

        filter_complex = (
            f"[1:a]volume={volume_db}dB,"
            f"adelay={delay_ms}|{delay_ms}[sfx];"
            f"[0:a]volume=2.0[voice];"
            f"[voice][sfx]amix=inputs=2:duration=first:dropout_transition=0"
        )
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                audio_path,
                "-i",
                sfx_path,
                "-filter_complex",
                filter_complex,
                "-c:a",
                "pcm_s16le",
                output_path,
            ]
        )
        return output_path

    def mix_sfx_batch(
        self,
        voice_path: str,
        sfx_list: list[dict],
        output_path: str,
    ) -> str:
        """Mix voice with ALL sfx using Python array math (reliable, no ffmpeg filter quirks).

        Each sfx dict: {file, time, volume_db}
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        valid = []
        for sfx in sfx_list:
            sfx_file = sfx.get("file", "")
            if not sfx_file or not os.path.exists(sfx_file):
                continue
            valid.append(sfx)

        if not valid:
            import shutil

            shutil.copy2(voice_path, output_path)
            return output_path

        import wave
        import array
        import math

        with wave.open(voice_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            voice_raw = wf.readframes(n_frames)

        if sampwidth != 2:
            logger.warning(
                "voice is %d-byte samples, expected 2; skipping sfx",
                sampwidth,
            )
            import shutil

            shutil.copy2(voice_path, output_path)
            return output_path

        voice_samples = array.array("h")
        voice_samples.frombytes(voice_raw)
        voice_dur = n_frames / framerate

        for sfx in valid:
            sfx_file = sfx["file"]
            position = sfx.get("time", 0)
            volume_db = sfx.get("volume_db", -10)

            try:
                with wave.open(sfx_file, "rb") as sf:
                    sfr = sf.getframerate()
                    sch = sf.getnchannels()
                    s_frames = sf.getnframes()
                    sfx_raw = sf.readframes(s_frames)
            except Exception as e:
                logger.warning("cannot read sfx %s: %s", sfx_file, e)
                continue

            sfx_samples = array.array("h")
            sfx_samples.frombytes(sfx_raw)

            if sch > 1:
                mono = array.array("h")
                for i in range(0, len(sfx_samples), sch):
                    chunk = sfx_samples[i : i + sch]
                    mono.append(sum(chunk) // sch)
                sfx_samples = mono

            if sfr != framerate:
                ratio = framerate / sfr
                resampled = array.array("h")
                for i in range(int(len(sfx_samples) / ratio)):
                    src_idx = int(i * ratio)
                    if src_idx < len(sfx_samples):
                        resampled.append(sfx_samples[src_idx])
                sfx_samples = resampled

            gain = 10.0 ** (volume_db / 20.0)

            start_sample = int(position * framerate) * n_channels
            if start_sample >= len(voice_samples):
                continue

            for i, sample in enumerate(sfx_samples):
                target = start_sample + i * n_channels
                if target >= len(voice_samples):
                    break
                boosted = int(sample * gain)
                mixed = voice_samples[target] + boosted
                if mixed > 32767:
                    mixed = 32767
                elif mixed < -32768:
                    mixed = -32768
                voice_samples[target] = mixed

            logger.debug(
                "sfx overlay: %.2fs %s vol=%.0fdB gain=%.2f",
                position,
                os.path.basename(sfx_file),
                volume_db,
                gain,
            )

        with wave.open(output_path, "wb") as out:
            out.setnchannels(n_channels)
            out.setsampwidth(sampwidth)
            out.setframerate(framerate)
            out.writeframes(voice_samples.tobytes())

        logger.info(
            "mix_sfx_batch: overlaid %d sfx onto voice (%.1fs) -> %s",
            len(valid),
            voice_dur,
            os.path.basename(output_path),
        )
        return output_path

        voice_dur = self.get_duration(voice_path)

        inputs = ["-i", voice_path]
        filter_parts = []
        sfx_labels = []

        for i, sfx in enumerate(valid):
            idx = i + 1
            sfx_file = sfx["file"]
            position = sfx.get("time", 0)
            volume_db = sfx.get("volume_db", -10)

            inputs.extend(["-i", sfx_file])

            sfx_dur = self.get_duration(sfx_file)
            delay_ms = int(position * 1000)
            if position + sfx_dur > voice_dur + 0.05:
                delay_ms = int(max(0, voice_dur - sfx_dur - 0.02) * 1000)

            label = f"s{i}"
            filter_parts.append(
                f"[{idx}:a]volume={volume_db}dB,"
                f"adelay={delay_ms}|{delay_ms},"
                f"apad=whole_dur={voice_dur:.3f},"
                f"atrim=duration={voice_dur:.3f}[{label}]"
            )
            sfx_labels.append(f"[{label}]")

        n_sfx = len(valid)
        sfx_chain = "".join(sfx_labels)
        pan_coeffs = "+".join(f"c{j}" for j in range(n_sfx))
        filter_parts.append(
            f"{sfx_chain}amerge=inputs={n_sfx},pan=mono|c0={pan_coeffs}[sfxtrack]"
        )

        filter_parts.append("[0:a][sfxtrack]amerge=inputs=2,pan=mono|c0=c0+c1[out]")

        filter_complex = ";".join(filter_parts)

        cmd = [
            self.ffmpeg,
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            output_path,
        ]
        self._run(cmd)
        return output_path

        audio_dur = self.get_duration(voice_path)

        inputs = ["-i", voice_path]
        filter_parts = []
        mix_labels = ["[voice_boost]"]

        filter_parts.append("[0:a]volume=2.0[voice_boost]")

        for i, sfx in enumerate(valid):
            idx = i + 1
            sfx_file = sfx["file"]
            position = sfx.get("time", 0)
            volume_db = sfx.get("volume_db", -10)

            inputs.extend(["-i", sfx_file])

            sfx_dur = self.get_duration(sfx_file)
            delay_ms = int(position * 1000)
            if position + sfx_dur > audio_dur + 0.05:
                delay_ms = int(max(0, audio_dur - sfx_dur - 0.02) * 1000)

            label = f"sfx{i}"
            filter_parts.append(
                f"[{idx}:a]volume={volume_db}dB,adelay={delay_ms}|{delay_ms}[{label}]"
            )
            mix_labels.append(f"[{label}]")

        n_inputs = len(valid) + 1
        mix_chain = "".join(mix_labels)
        filter_parts.append(
            f"{mix_chain}amix=inputs={n_inputs}:duration=first:dropout_transition=0"
        )

        filter_complex = ";".join(filter_parts)

        cmd = [
            self.ffmpeg,
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-c:a",
            "pcm_s16le",
            output_path,
        ]
        self._run(cmd)
        return output_path

    def normalize_audio(
        self, input_path: str, output_path: str, target_db: float = -1.0
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            self._run(
                [
                    self.ffmpeg,
                    "-y",
                    "-i",
                    input_path,
                    "-af",
                    f"loudnorm=I={target_db}:TP=-1:LRA=11",
                    "-c:a",
                    "pcm_s16le",
                    output_path,
                ]
            )
        except Exception:
            logger.warning(
                "loudnorm not supported, falling back to volume normalization"
            )
            self._run(
                [
                    self.ffmpeg,
                    "-y",
                    "-i",
                    input_path,
                    "-af",
                    "dynaudnorm",
                    "-c:a",
                    "pcm_s16le",
                    output_path,
                ]
            )
        return output_path

    def crossfade_concat(
        self, input_files: list[str], output_path: str, crossfade_dur: float = 0.04
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if len(input_files) < 2:
            if input_files:
                import shutil

                shutil.copy2(input_files[0], output_path)
            return output_path

        filter_parts = []
        n = len(input_files)
        inputs = []
        for f in input_files:
            inputs.extend(["-i", f])

        if n == 2:
            filter_parts.append(
                f"[0:a][1:a]acrossfade=d={crossfade_dur:.3f}:c1=tri:c2=tri[aout]"
            )
        else:
            prev = "[0:a]"
            for i in range(1, n):
                out_label = f"[aout]" if i == n - 1 else f"[a{i}]"
                filter_parts.append(
                    f"{prev}[{i}:a]acrossfade=d={crossfade_dur:.3f}:c1=tri:c2=tri{out_label}"
                )
                prev = out_label

        filter_complex = ";".join(filter_parts)
        cmd = (
            [self.ffmpeg, "-y"]
            + inputs
            + [
                "-filter_complex",
                filter_complex,
                "-map",
                "[aout]",
                "-c:a",
                "pcm_s16le",
                output_path,
            ]
        )
        self._run(cmd)
        return output_path

    def mute_segments(
        self, input_path: str, output_path: str, mute_ranges: list[tuple[float, float]]
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if not mute_ranges:
            import shutil

            shutil.copy2(input_path, output_path)
            return output_path

        parts = []
        for start, end in mute_ranges:
            parts.append(f"volume=0:enable='between(t,{start:.3f},{end:.3f})'")
        filter_str = ",".join(parts)

        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                input_path,
                "-af",
                filter_str,
                "-c:a",
                "pcm_s16le",
                output_path,
            ]
        )
        return output_path

    def compress_silence(
        self,
        input_path: str,
        output_path: str,
        threshold_db: float = -40,
        min_silence_dur: float = 0.5,
        compression_ratio: float = 0.25,
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                input_path,
                "-af",
                (
                    f"silenceremove=stop_periods=-1"
                    f":stop_duration={min_silence_dur}"
                    f":stop_threshold={threshold_db}dB"
                    f":start_periods=1"
                    f":start_duration=0"
                    f":start_threshold={threshold_db}dB"
                ),
                "-c:a",
                "pcm_s16le",
                output_path,
            ]
        )
        return output_path
