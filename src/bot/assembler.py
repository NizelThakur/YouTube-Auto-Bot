import glob
import os
import re
import subprocess
import sys

from imageio_ffmpeg import get_ffmpeg_exe


class Assembler:
    def __init__(self, config, build_dir: str):
        self.cfg = config
        self.build_dir = build_dir
        self.ffmpeg = get_ffmpeg_exe()

    # ------------------------------------------------------------------ #
    #  DURATION DETECTION — uses ffmpeg stderr (works on ALL builds)
    # ------------------------------------------------------------------ #

    def get_duration(self, path: str) -> float:
        """
        Parse 'Duration: HH:MM:SS.ss' from ffmpeg stderr.
        This works on ALL ffmpeg builds including static binaries
        where ffprobe may not exist as a separate executable.
        """
        try:
            result = subprocess.run(
                [self.ffmpeg, "-i", path],
                capture_output=True, text=True
            )
            # ffmpeg prints file info to stderr even when no output is given
            match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", result.stderr)
            if match:
                h = int(match.group(1))
                m = int(match.group(2))
                s = float(match.group(3))
                dur = h * 3600 + m * 60 + s
                return dur
        except Exception as e:
            print(f"  WARNING: get_duration failed for {os.path.basename(path)}: {e}")
        return None

    # ------------------------------------------------------------------ #
    #  STEP 1 — Scale & crop all bg clips to 1080x1920 portrait
    # ------------------------------------------------------------------ #

    def format_clips(self) -> list:
        bg_files = sorted(glob.glob(os.path.join(self.build_dir, "bg_*.mp4")))
        if not bg_files:
            raise Exception("No background video files (bg_*.mp4) found in build dir!")

        print(f"  Cropping {len(bg_files)} clips to 1080x1920 portrait...")
        formatted = []
        for src in bg_files:
            out = os.path.join(self.build_dir, f"fmt_{os.path.basename(src)}")
            subprocess.run(
                [
                    self.ffmpeg, "-y", "-i", src,
                    "-vf", (
                        "scale=1080:1920:force_original_aspect_ratio=increase,"
                        "crop=1080:1920,"
                        "fps=30,"
                        "setsar=1"
                    ),
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-an",  # no audio in background clips
                    out,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            formatted.append(out)
            print(f"    Formatted: {os.path.basename(out)}")

        return formatted

    # ------------------------------------------------------------------ #
    #  STEP 2 — Loop clips to cover audio duration
    # ------------------------------------------------------------------ #

    def loop_background(self, clips: list, audio_dur: float) -> str:
        # Measure total clip duration
        total_clip_dur = 0.0
        for c in clips:
            d = self.get_duration(c)
            total_clip_dur += d if d else 5.0

        if total_clip_dur <= 0:
            total_clip_dur = len(clips) * 5.0

        # Create enough loops so bg is definitely longer than audio
        loops = max(3, int((audio_dur / total_clip_dur) * 2) + 2)
        estimated = loops * total_clip_dur
        print(f"  Audio={audio_dur:.1f}s | Clips={total_clip_dur:.1f}s | Loops={loops}x → ~{estimated:.1f}s bg")

        concat_txt = os.path.join(self.build_dir, "concat.txt")
        with open(concat_txt, "w") as f:
            for _ in range(loops):
                for c in clips:
                    # Use basename only — ffmpeg concat runs from build_dir
                    f.write(f"file '{os.path.basename(c)}'\n")

        merged = os.path.join(self.build_dir, "merged_bg.mp4")
        subprocess.run(
            [
                self.ffmpeg, "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_txt,
                "-c", "copy",
                merged,
            ],
            cwd=self.build_dir,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"  Background loop created: {os.path.basename(merged)}")
        return merged

    # ------------------------------------------------------------------ #
    #  STEP 3 — Merge video + voiceover + subtitles, trim to audio length
    # ------------------------------------------------------------------ #

    @staticmethod
    def _escape_ffmpeg_path(path: str) -> str:
        """
        Escape a file path for use inside ffmpeg filter expressions.
        ffmpeg's libass subtitle filter needs:
          - backslashes escaped (Windows paths)
          - colons escaped       (Windows drive letters like C:)
          - single-quotes escaped
        """
        path = path.replace("\\", "/")       # convert to forward slashes
        path = path.replace(":", "\\:")       # escape colons for libass
        path = path.replace("'", "'\\''")     # escape single quotes
        return path

    def assemble_final(self, bg: str, audio_dur: float) -> str:
        audio = os.path.join(self.build_dir, "audio.mp3")
        vtt = os.path.join(self.build_dir, "subtitles.vtt")
        output = os.path.join(self.build_dir, "final_short.mp4")

        style = self.cfg.get(
            "video", "subtitle_style",
            default="Fontname=Liberation Sans,FontSize=18,PrimaryColour=&H00FFFFFF,"
                    "OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=1"
        )

        print(f"  Merging video + audio + subtitles → {audio_dur:.1f}s final video...")

        # Build the subtitle filter.
        # Use absolute path (escaped for ffmpeg) so it works regardless of cwd.
        escaped_vtt = self._escape_ffmpeg_path(os.path.abspath(vtt))
        sub_filter = f"subtitles={escaped_vtt}:force_style='{style}'"

        # CRITICAL:
        #   -i bg           = input 0 (video stream)
        #   -i audio        = input 1 (audio stream)
        #   -map 0:v:0      = take video from input 0
        #   -map 1:a:0      = take audio from input 1
        #   -t audio_dur    = OUTPUT option (comes AFTER inputs) — limits output
        cmd = [
            self.ffmpeg, "-y",
            "-i", bg,
            "-i", audio,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vf", sub_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(audio_dur),
            "-movflags", "+faststart",
            output,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ffmpeg stderr:\n{result.stderr[-2000:]}")
            raise Exception(f"ffmpeg assembly failed (exit code {result.returncode})")

        print(f"  ✅ Final video: {os.path.basename(output)} ({audio_dur:.1f}s)")
        return output

    # ------------------------------------------------------------------ #
    #  ENTRY POINT
    # ------------------------------------------------------------------ #

    def run(self) -> str:
        print("--- [2/3] ASSEMBLY ---")

        audio = os.path.join(self.build_dir, "audio.mp3")
        audio_dur = self.get_duration(audio)

        if not audio_dur or audio_dur <= 0:
            raise Exception(
                f"Cannot determine audio duration for {audio}. "
                "Check if audio.mp3 was generated correctly."
            )

        print(f"  Audio duration confirmed: {audio_dur:.2f}s")

        clips = self.format_clips()
        bg = self.loop_background(clips, audio_dur)
        final = self.assemble_final(bg, audio_dur)

        print("[2/3] Assembly complete.\n")
        return final
