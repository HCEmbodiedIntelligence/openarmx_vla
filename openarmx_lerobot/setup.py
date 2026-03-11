from setuptools import setup
import os
from glob import glob

package_name = "openarmx_lerobot"

setup(
    name=package_name,
    version="0.0.1",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="openarmx",
    maintainer_email="user@example.com",
    description="Combined launch for OpenArmX bringup + pico pose bridge + teleop by Pico",
    license="CC-BY-NC-SA-4.0",
    tests_require=["pytest"],
    entry_points={},
)
