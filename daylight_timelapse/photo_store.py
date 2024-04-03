#!/usr/bin/env python3
import asyncio
from pathlib import Path
import datetime as dt

import click
import appdirs

from async_app.app import AsyncApp
from async_app.logger import logger
import async_app.messenger as app_messenger
from async_app.app_factory import async_app_options


def new_photo(record):
    camera_name = record["camera_name"]
    command = record["command"]
    if command == "add_image":
        # TODO: add timezone info
        # TODO: add image type
        ts = record["ts"]
        image_data = record["image_data"]
        image_type = record["image_type"]

        if not image_data:
            logger.warning("Record contained no image data.")
            return

        logger.debug(
            f"Received new image for {camera_name} with {len(image_data)} bytes."
        )

        app_dirs = appdirs.AppDirs(appname="daylight-timelapse")

        photos_base_dir = Path(app_dirs.user_data_dir) / "photos"

        now = dt.datetime.fromtimestamp(ts)
        year_str = f"{now:%Y}"
        today_str = f"{now:%Y%m%d}"

        todays_photos_dir = photos_base_dir / year_str / today_str / camera_name
        todays_photos_dir.mkdir(exist_ok=True, parents=True)

        file_name = (
            todays_photos_dir / f"{camera_name}-{now:%Y%m%d-%H%M%S}.{image_type}"
        )
        with file_name.open("wb") as fd:
            fd.write(image_data)
        logger.debug(f"Saved new image to {file_name.as_posix()}.")


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
            "args": (f"daily-timelapse:{camera_name}:command", new_photo),
        }
    ]
    for task_description in task_descriptions:
        app.add_task_description(task_description)

    asyncio.run(app.run())  # , debug=True)


if __name__ == "__main__":
    main()
