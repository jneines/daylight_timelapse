"""Main module."""

import asyncio
import time
import datetime as dt
import requests
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun

import click

from async_app.app import AsyncApp
from async_app.logger import logger
import async_app.messenger as app_messenger
from async_app.app_factory import async_app_options


async def initialize(camera_name):
    logger.info("Initializing")

    state_record = {
        "ts": time.time(),
        "camera_name": camera_name,
        "state": "idle",
    }
    await app_messenger.set(f"daily-timelapse:{camera_name}:state", state_record)


async def start_at(camera_name, start_dt):
    logger.info(f"Start is scheduled at {start_dt.isoformat()}")
    tz = start_dt.tzinfo

    now = dt.datetime.now(tz)
    wait_for = max(0, (start_dt - now).total_seconds())
    logger.info(f"Waiting {wait_for} seconds to start.")
    await asyncio.sleep(wait_for)

    logger.info("Now starting.")

    cmd_record = {
        "ts": time.time(),
        "camera_name": camera_name,
        "command": "start",
    }
    await app_messenger.publish(f"daily-timelapse:{camera_name}:command", cmd_record)

    state_record = {
        "ts": time.time(),
        "camera_name": camera_name,
        "state": "running",
    }
    await app_messenger.set(f"daily-timelapse:{camera_name}:state", state_record)


async def stop_at(camera_name, stop_dt):
    logger.info(f"Stop is scheduled at {stop_dt.isoformat()}")

    tz = stop_dt.tzinfo
    now = dt.datetime.now(tz)
    wait_for = max(0, (stop_dt - now).total_seconds())
    logger.info(f"Waiting {wait_for} seconds to stop.")
    await asyncio.sleep(wait_for)

    logger.info("Now stopping.")

    cmd_record = {
        "ts": time.time(),
        "camera_name": camera_name,
        "command": "stop",
    }
    await app_messenger.publish(f"daily-timelapse:{camera_name}:command", cmd_record)

    state_record = {
        "ts": time.time(),
        "camera_name": camera_name,
        "state": "idle",
    }
    await app_messenger.set(f"daily-timelapse:{camera_name}:state", state_record)

    app_state.keep_running = False


async def fetch_image(camera_name):
    state_record = await app_messenger.get(f"daily-timelapse:{camera_name}:state")
    if state_record["state"] != "running":
        return

    logger.info(f"Fetching next image from {camera_name}")
    snapshot_url = f"http://{camera_name}:8080/snapshot"

    r = requests.get(snapshot_url, stream=True)
    if r.status_code == 200:
        image_data = r.content
        logger.debug(f"Fetched image has {len(image_data)} Bytes.")
        cmd_record = {
            "ts": time.time(),
            "camera_name": camera_name,
            "command": "add_image",
            "image_data": image_data,
            "image_type": "jpg",
        }
        await app_messenger.publish(
            f"daily-timelapse:{camera_name}:command", cmd_record
        )
    else:
        logger.error(f"Unable to fetch image. Reason was {r.status_code}.")


@click.command
@async_app_options
@click.option(
    "-n",
    "--camera-name",
    type=str,
    required=True,
    help="Camera name to be used in requests fetch url.",
)
@click.option(
    "-e",
    "--every",
    type=int,
    default=30,
    show_default=True,
    help="Fetch photos every 'every' secondsl.",
)
@click.option(
    "-lat",
    "--latitude",
    type=float,
    default=52.52437,
    show_default=True,
    help="Latitude of location to be used for sunrise/sunset calculation.",
)
@click.option(
    "-lon",
    "--longitude",
    type=float,
    default=13.41053,
    show_default=True,
    help="Longitude of location to be used for sunrise/sunset calculation.",
)
@click.option(
    "-tz",
    "--timezone",
    type=str,
    default="Europe/Berlin",
    show_default=True,
    help="Timezone to be used.",
)
@click.option(
    "-fm",
    "--frame-margin",
    type=int,
    default=120,
    help="Number of additional frames taken before sunrise and after sunset in respect to the 'every' setting. The default setting results in a 1 hour margin for the default setting of 'every'.",
)
def main(**kwargs):
    camera_name = kwargs["camera_name"]
    every = kwargs["every"]
    latitude = kwargs["latitude"]
    longitude = kwargs["longitude"]
    timezone = kwargs["timezone"]
    frame_margin = kwargs["frame_margin"]

    # calculate start and end of the timelapse shoot
    tz = ZoneInfo(timezone)
    location = LocationInfo(
        name="Here", timezone=tz, latitude=latitude, longitude=longitude
    )

    now = dt.datetime.now()
    s = sun(location.observer, date=now.date(), tzinfo=location.timezone)

    sunrise_dt = s["sunrise"]
    sunset_dt = s["sunset"]
    logger.info(f"{sunrise_dt=}, {sunset_dt=}")

    start_dt = sunrise_dt - dt.timedelta(seconds=frame_margin * every)
    stop_dt = sunset_dt + dt.timedelta(seconds=frame_margin * every)
    logger.info(f"{start_dt=}, {stop_dt=}")

    app = AsyncApp(**kwargs)
    task_descriptions = [
        {
            "kind": "init",
            "function": initialize,
            "args": (camera_name,),
        },
        {
            "kind": "continuous",
            "function": start_at,
            "args": (
                camera_name,
                start_dt,
            ),
        },
        {
            "kind": "continuous",
            "function": stop_at,
            "args": (
                camera_name,
                stop_dt,
            ),
        },
        {
            "kind": "periodic",
            "function": fetch_image,
            "call_every": every,
            "args": (camera_name,),
        },
    ]

    for task_description in task_descriptions:
        app.add_task_description(task_description)

    asyncio.run(app.run())  # , debug=True)


if __name__ == "__main__":
    main()
