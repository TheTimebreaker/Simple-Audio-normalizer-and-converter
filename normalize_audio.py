import re, shutil, sys, os, subprocess, asyncio, configparser
from typing import Optional, Coroutine


config = configparser.ConfigParser()
config.read('config.ini')

semaphore_ffmpeg = asyncio.Semaphore(int(config['limits']['ffmpeg']))
semaphore_fileOperations = asyncio.Semaphore(int(config['limits']['fileOperations']))



async def deleteFile(path:str) -> None:
    async with semaphore_fileOperations:
        await asyncio.to_thread(os.remove, path)
async def moveFile(src:str, dst:str) -> None:
    async with semaphore_fileOperations:
        await asyncio.to_thread(shutil.move, src, dst)



async def get_max_volume(input_file:str, ffmpeg_subprocess_output:Optional[subprocess.CompletedProcess] = None) -> float:
    if ffmpeg_subprocess_output is None:
        cmd = [
            "ffmpeg", "-i", input_file,
            "-af", "volumedetect",
            "-f", "null", "-"
        ]
        async with semaphore_ffmpeg:
            result = await asyncio.to_thread(subprocess.run, cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    else:
        result = ffmpeg_subprocess_output
    match = re.search(r"max_volume:\s*(-?\d+\.?\d*) dB", result.stderr)
    if not match:
        raise RuntimeError("Could not find max_volume in ffmpeg output.")
    return float(match.group(1))

async def normalize(input_file:str, target_dBFS:float, target_bitrate:str = '128k') -> None:
    """Normalize the volume of the audio file recursively to avoid clipping."""
    base, extension = os.path.splitext(input_file)
    clip_file = input_file + "_temp.mp3"
    output_tmp = input_file + "_out.mp3"
    output_file = input_file.replace(extension, '.mp3')

    max_volume = await get_max_volume(input_file)
    is_clipped = round(max_volume, 1) == 0.0
    if is_clipped:
        clip_test_dB = -6
        cmd = [
            "ffmpeg", "-y", "-i", input_file,
            "-af", f"volume={clip_test_dB}dB,volumedetect",
            "-c:a", "libmp3lame", "-b:a", target_bitrate,
            clip_file
        ]
        async with semaphore_ffmpeg:
            print(f'Un-clipping {input_file} ...')
            result = await asyncio.to_thread(subprocess.run, cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
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
    await moveFile(input_file, backup_file)
    await moveFile(output_tmp, output_file)
    for file in (clip_file, backup_file):
        try:
            await deleteFile(file)
        except FileNotFoundError:
            pass

async def main(files:list[str]) -> None:
    tasks:list[Coroutine] = []
    for filepath in files:
        if os.path.isfile(filepath):
            tasks.append(normalize(filepath, float(config['DEFAULTS']['targetdBFS']), config['DEFAULTS']['bitrate']))
        else:
            raise Exception(f'{filepath} is not a file.')
    
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Drag and drop one or more audio files onto this script.")
        input("Press Enter to exit.")
        sys.exit(1)

    asyncio.run(main(sys.argv[1:]))
    input('Done... ')