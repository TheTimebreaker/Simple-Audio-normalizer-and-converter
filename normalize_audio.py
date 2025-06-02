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
    config_path = os.path.join(base_path, 'config.ini')
    if os.path.isfile(config_path):
        return config_path
    return os.path.join(base_path, 'config_default.ini')


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
async def get_duration_seconds(input_file:str) -> float:
    """Returns the duration of given audio file in seconds.

    Args:
        input_file (str): Path to filoe

    Returns:
        float: Duration of audio in seconds
    """
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format',
        'compact=print_section=0:nokey=1:escape=csv',
        '-show_entries',
        'format=duration',
        input_file
    ]
    async with semaphore_ffmpeg:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            encoding= 'utf-8'
        )
    return float(result.stdout.strip())

async def normalize(input_file:str) -> str:
    """Normalize the volume of the audio file recursively to avoid clipping.
    Returns:
        str: Path to output file
    """
    clip_file = input_file + ".clipping-tmp.mp3"
    output_file = input_file + '.normalized.wav'
    target_dBFS = float(config['normalize']['targetdBFS']) #pylint:disable=invalid-name
    target_bitrate = config['GENERAL']['bitrate']


    clip_test_dB = -6 #pylint:disable=invalid-name
    cmd = [
        "ffmpeg", "-y", "-i", input_file,
        '-loglevel', 'error',
        "-af", f"volume={clip_test_dB}dB",
        "-c:a", "libmp3lame", "-b:a", target_bitrate,
        clip_file
    ]
    async with semaphore_ffmpeg:
        print(f'Un-clipping {input_file} ...')
        await asyncio.to_thread(
            subprocess.run,
            cmd,
        )
    max_volume = await get_max_volume(clip_file) - clip_test_dB


    async with semaphore_ffmpeg:
        print(f'Normalizing {input_file} ...')
        await asyncio.to_thread(subprocess.run, [
            "ffmpeg", "-y", "-i", input_file,
            '-loglevel', 'error',
            "-af", f"volume={target_dBFS - max_volume}dB",
            output_file
        ])


    for file in (clip_file, ):
        try:
            await delete_file(file)
        except FileNotFoundError:
            pass
    return output_file
async def remove_silence(input_file:str) -> str:
    """Normalize the volume of the audio file recursively to avoid clipping.
    Returns:
        str: Path to output file
    """
    silenceremove_file = input_file + ".silenceremoved-tmp.wav"
    output_file = input_file + '.silenceremoved.wav'

    # variable names according to https://ffmpeg.org/ffmpeg-filters.html#silenceremove
    # these are named for the removal of silence at the beginning, but are used for the end as well
    start_duration = 0
    start_threshold_dB = int(config['remove-silence']['silence_threshold_dB'])#pylint:disable=invalid-name
    start_silence = float(config['remove-silence']['keep_silence_seconds'])

    silenceremove_parameters = f'1:{start_duration}:{start_threshold_dB}dB:{start_silence}'
    async with semaphore_ffmpeg:
        print(f'Removing silence {input_file} ...')
        await asyncio.to_thread(subprocess.run, [
            "ffmpeg", "-y", "-i", input_file,
            '-loglevel', 'error',
            "-af", (    # silence remover is strange and can sometimes remove song parts if used
                        # at the end using the proper end parameters. using areverse (turns audio
                        # backwards), this is a non-isse, since the start remover works fine
                        f'adelay={int(start_silence)+1}s:all=true,'
                        f'silenceremove={silenceremove_parameters},'
                        'areverse,'
                        f'adelay={int(start_silence)+1}s:all=true,'
                        f'silenceremove={silenceremove_parameters},'
                        'areverse'
                    ),
            silenceremove_file
        ])

    duration_seconds:float = await get_duration_seconds(silenceremove_file)
    async with semaphore_ffmpeg:
        print(f'Applying fades {input_file} ...')
        await asyncio.to_thread(subprocess.run, [
            "ffmpeg", "-y", "-i", silenceremove_file,
            '-loglevel', 'error',
            "-af", (
                        f'afade=t=in:ss=0:d={start_silence},'
                        f'afade=t=out:st={duration_seconds - start_silence}:d={start_silence}'
                    ),
            output_file
        ])

    for file in (silenceremove_file, ):
        try:
            await delete_file(file)
        except FileNotFoundError:
            pass
    return output_file

async def final_conversion(input_file:str, output_file:str) -> None:
    """Final conversion function for audio files.

    Args:
        input_file (str): Path for input file.
        output_file (str): Path for output file.
    """
    async with semaphore_ffmpeg:
        await asyncio.to_thread(subprocess.run, [
            "ffmpeg", "-y", "-i", input_file,
            '-loglevel', 'error',
            "-c:a", "libmp3lame", "-b:a", config['GENERAL']['bitrate'],
            output_file
        ])

async def process_file(input_file:str) -> None:
    """Main function that runs all the processing functions you want on a file.

    Args:
        input_file (str): Path to file
    """
    base, _ = os.path.splitext(input_file)
    final_output = base + '.mp3'
    final_output_tmp = final_output + '.tmp.mp3'
    cleanup_files:list[str] = [input_file]


    input_file = await remove_silence(
        input_file
    )
    cleanup_files.append(input_file)


    input_file = await normalize(
        input_file
    )
    cleanup_files.append(input_file)


    await final_conversion(
        input_file, final_output_tmp
    )


    for file in cleanup_files:
        try:
            await delete_file(file)
        except FileNotFoundError:
            pass
    await move_file(final_output_tmp, final_output)

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
