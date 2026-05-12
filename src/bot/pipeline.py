import os
import tempfile
import traceback

from .assembler import Assembler
from .config import Config
from .generator import Generator
from .uploader import Uploader


class Pipeline:
    def __init__(self, profile_name: str, base_dir: str = "."):
        self.profile_name = profile_name
        self.cfg = Config(profile_name, base_dir)

    def run(self, dry_run: bool = False):
        print(f"\n{'='*55}")
        print(f"  PIPELINE: {self.profile_name.upper()}")
        print(f"  Dry Run : {dry_run}")
        print(f"{'='*55}\n")

        with tempfile.TemporaryDirectory(prefix=f"ytbot_{self.profile_name}_") as build_dir:
            print(f"  Build dir: {build_dir}\n")
            try:
                # Stage 1: Generate story, audio, backgrounds
                Generator(self.cfg, build_dir).run()

                # Stage 2: Assemble final video
                Assembler(self.cfg, build_dir).run()

                # Stage 3: Upload to YouTube
                Uploader(self.cfg, build_dir).run(dry_run=dry_run)

                print(f"{'='*55}")
                print(f"  [OK] PIPELINE SUCCESS: {self.profile_name.upper()}")
                print(f"{'='*55}\n")

            except Exception as e:
                print(f"\n{'='*55}")
                print(f"  [FAIL] PIPELINE FAILED: {self.profile_name.upper()}")
                print(f"  Error: {e}")
                print(f"--- Traceback ---")
                traceback.print_exc()
                print(f"{'='*55}\n")
                raise
