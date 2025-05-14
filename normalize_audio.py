import re
import shutil
import sys
import os
import subprocess
import asyncio
import configparser
from typing import Optional, Coroutine


def get_config_path() -> str:
    """Returns path of config.ini file in a way that works with pyinstaller."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS #type:ignore #pylint:disable=protected-access
    else:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, 'config.ini')

config = configparser.ConfigParser()
config.read(get_config_path())

semaphore_ffmpeg = asyncio.Semaphore(int(config['limits']['ffmpeg']))
semaphore_fileOperations = asyncio.Semaphore(int(config['limits']['fileOperations']))



async def delete_file(path:str) -> None:
    """Asynchronously deletes a file."""
    async with semaphore_fileOperations:
        await asyncio.to_thread(os.remove, path)
async def move_file(src:str, dst:str) -> None:
    """Asynchronously moves a file."""
    async with semaphore_fileOperations:
        await asyncio.to_thread(shutil.move, src, dst)



async def get_max_volume(
        input_file:str,
        ffmpeg_subprocess_output:Optional[subprocess.CompletedProcess] = None
    ) -> float:
    """Returns the maximum volume (in dBFS) of a given file.

    Args:
        input_file (str): Filepath to file
        ffmpeg_subprocess_output: Accepts the output of a subprocess.PIPE call.
        This can save one ffmpeg call when run after a conversion. Defaults to None.

    Returns:
        float: Maximum volume of the file.
    """
    if ffmpeg_subprocess_output is None:
        cmd = [
            "ffmpeg", "-i", input_file,
            "-af", "volumedetect",
            "-f", "null", "-"
        ]
        async with semaphore_ffmpeg:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                encoding= 'utf-8'
            )
    else:
        result = ffmpeg_subprocess_output
    match = re.search(r"max_volume:\s*(-?\d+\.?\d*) dB", result.stderr)
    if not match:
        raise RuntimeError("Could not find max_volume in ffmpeg output.")
    return float(match.group(1))

async def normalize(
        input_file:str,
        target_dBFS:float, #pylint:disable=invalid-name
        target_bitrate:str = '128k'
    ) -> None:
    """Normalize the volume of the audio file recursively to avoid clipping."""
    _, extension = os.path.splitext(input_file)
    clip_file = input_file + "_temp.mp3"
    output_tmp = input_file + "_out.mp3"
    output_file = input_file.replace(extension, '.mp3')

    max_volume = await get_max_volume(input_file)
    is_clipped = round(max_volume, 1) == 0.0
    if is_clipped:
        clip_test_dB = -6 #pylint:disable=invalid-name
        cmd = [
            "ffmpeg", "-y", "-i", input_file,
            "-af", f"volume={clip_test_dB}dB,volumedetect",
            "-c:a", "libmp3lame", "-b:a", target_bitrate,
            clip_file
        ]
        async with semaphore_ffmpeg:
            print(f'Un-clipping {input_file} ...')
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                encoding= 'utf-8'
            )
        max_volume = await get_max_volume(clip_file, result) - clip_test_dB

    async with semaphore_ffmpeg:
        print(f'Normalizing {input_file} ...')
        await asyncio.to_thread(subprocess.run, [
            "ffmpeg", "-y", "-i", input_file,
            '-loglevel', 'error',
            "-af", f"volume={target_dBFS - max_volume}dB,volumedetect",
            "-c:a", "libmp3lame", "-b:a", target_bitrate,
            output_tmp
        ])

    backup_file = input_file + '.tmp'
    await move_file(input_file, backup_file)
    await move_file(output_tmp, output_file)
    for file in (clip_file, backup_file):
        try:
            await delete_file(file)
        except FileNotFoundError:
            pass
async def process_file(input_file:str) -> None:
    """Main function that runs all the processing functions you want on a file.

    Args:
        input_file (str): Path to file
    """
    await normalize(
        input_file,
        float(config['DEFAULTS']['targetdBFS']),
        config['DEFAULTS']['bitrate']
    )

async def main(files:list[str]) -> None:
    """Processes all files given.

    Args:
        files (list[str]): List of files.

    Raises:
        FileNotFoundError: Risen when one of the paths given does not lead to a file.
    """
    tasks:list[Coroutine] = []
    for filepath in files:
        if os.path.isfile(filepath):
            tasks.append(process_file(filepath))
        else:
            raise FileNotFoundError(f'{filepath} is not a file.')

    await asyncio.gather(*tasks)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Drag and drop one or more audio files onto this script.")
        input("Press Enter to exit.")
        sys.exit(1)

    asyncio.run(main(sys.argv[1:]))
    input('Done... ')
