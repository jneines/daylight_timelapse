#!/usr/bin/env python3
import asyncio
import contextlib
from pathlib import Path
import datetime as dt
import shlex

import click
import appdirs

from async_app.app import AsyncApp
from async_app.logger import logger
import async_app.messenger as app_messenger
from async_app.app_factory import async_app_options


#
# central dispatcher for commands
#
async def run_command(record):
    """The central dispatcher for command records."""

    command = record["command"]
    camera_name = record["camera_name"]

    if command == "start":
        logger.info("Start requested")
        await start_video_processor(camera_name)
    elif command == "stop":
        logger.info("Stop requested")
        await stop_video_processor(camera_name)
    elif command == "add_image":
        logger.info("add_image requested.")
        await add_image(record)

    else:
        logger.warning(f"Ignoring unknown command {command}")


#
# video processor related
#
video_processors = {}


#
# a little helper method
#
async def is_running(process):
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(process.wait(), 1e-6)
    return process.returncode is None


async def get_ffmpeg(camera_name):
    global video_processors

    try:
        ffmpeg = video_processors[camera_name]
    except KeyError:
        logger.warning(f"No ffmpeg process found for {camera_name}.")
        return None

    # Entry might exist, but can be set to None from a clean up
    # We might as well check if the entry is a process type.
    if ffmpeg is None:
        return None

    # In case we have a handle to the ffmpeg process, check if its running
    if await is_running(ffmpeg):
        return ffmpeg
    else:
        return None


async def start_video_processor(camera_name):
    global video_processors

    ffmpeg = await get_ffmpeg(camera_name)
    if ffmpeg:
        logger.warning(
            f"An ffmpeg process for {camera_name} already exists. Re-using it."
        )
        return

    logger.info(f"Starting new video_processor for {camera_name}")

    app_dirs = appdirs.AppDirs(appname="daylight-timelapse")

    video_base_dir = Path(app_dirs.user_data_dir) / "videos"
    logs_base_dir = Path(app_dirs.user_data_dir) / "logs"

    now = dt.datetime.now()
    year_str = f"{now:%Y}"
    today_str = f"{now:%Y%m%d}"
    now_str = f"{now:%Y%m%d-%H%M%S}"

    video_dir = video_base_dir / year_str / today_str
    video_dir.mkdir(exist_ok=True, parents=True)

    logs_dir = logs_base_dir / year_str / today_str
    logs_dir.mkdir(exist_ok=True, parents=True)

    video_path = video_dir / f"{camera_name}-{now_str}.mp4"

    # ENV='FFREPORT=file="./%p-%t.log":level=32'
    # NOTE: The '-vf format=yuv420p' setting is essential in order
    # to later play material via dlna to samsung tvs.
    # The '-movflags ...' set of parameters let ffmpeg create a fragmented
    # mp4 file. This ensures the file to be playable even if the video is
    # not completed (e.g. after write failures, network errors ...)
    ffmpeg_log_file = (logs_dir / "%p-%t.log").as_posix()
    cmd = (
        "/usr/bin/ffmpeg -y "
        "-hide_banner "
        "-report "
        "-nostats "
        "-f image2pipe -i pipe:0 "
        "-f lavfi -i anullsrc -c:a aac "
        "-filter:v scale=1280:720 "
        # "-b:v 4M -c:v h264 -profile:v high422 "
        #"-b:v 4M -c:v h264 -preset slow -crf 22 "
        "-b:v 2M -c:v h264 -preset slow -crf 25 -vf format=yuv420p "
        "-movflags +frag_keyframe+separate_moof+omit_tfhd_offset+empty_moov "
        "-shortest "
        f"{video_path}"
    )
    logger.info(f"Using ffmpeg like this: {cmd}.")

    args = shlex.split(cmd)
    try:
        ffmpeg = await asyncio.subprocess.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env={"FFREPORT": f"file={ffmpeg_log_file}:level=32"},
        )
        video_processors[camera_name] = ffmpeg

    except (FileNotFoundError,) as e:
        # asyncio.subprocess.SubprocessError) as e:
        logger.error(f"Error starting the video processor. Error message was {e}")


async def stop_video_processor(camera_name):
    global video_processors

    logger.info(f"Stopping video processor for {camera_name}")

    ffmpeg = await get_ffmpeg(camera_name)
    if not ffmpeg:
        logger.error("There does not seem to be a running ffmpeg process.")
        return

    logger.info(f"Finishing video for {camera_name}.")
    await ffmpeg.stdin.drain()
    ffmpeg.stdin.close()
    await ffmpeg.wait()
    # app_state.keep_running = False
    video_processors[camera_name] = None


async def add_image(record):
    global video_processors

    camera_name = record["camera_name"]
    image_data = record["image_data"]

    logger.info(f"Received an image from {camera_name} with {len(image_data)} Bytes.")

    ffmpeg = await get_ffmpeg(camera_name)
    if not ffmpeg:
        logger.warning(
            f"There does not seem to be a running ffmpeg process. Try to start one."
        )
        await start_video_processor(camera_name)
        ffmpeg = await get_ffmpeg(camera_name)

    # feed image into ffmpeg
    ffmpeg.stdin.write(image_data)
    await ffmpeg.stdin.drain()


@click.command()
@async_app_options
@click.option(
    "-n", "--camera-name", type=str, required=True, help="Camera name to use for video."
)
def main(**kwargs):
    camera_name = kwargs["camera_name"]

    app = AsyncApp(**kwargs)
    task_descriptions = [
        {
            "kind": "continuous",
            "function": app_messenger.listener,
            "args": (f"daily-timelapse:{camera_name}:command", run_command),
        }
    ]
    for task_description in task_descriptions:
        app.add_task_description(task_description)

    asyncio.run(app.run())  # , debug=True)


if __name__ == "__main__":
    main()
