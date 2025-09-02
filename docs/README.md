# Blucifer
*A Discord bot to handle volunteer registration for 7th Circle Music Collective*

## What is Blucifer? 
Blucifer is a Discord bot that handles volunteer registration for 7th Circle Music Collective. More exactly, it creates lists of upcoming shows (events on a google calendar), threads to coordinate volunteers within a show, and more. 

## Installation Instructions
If installing for a group, it is recommended to put the bot on a Linux server. All commands given will assume you're operating on Linux. 

First, clone the git repository into an empty directory. Use `git clone https://github.com/thecocohead/blucifer <directory>` to download the code. 

Next, a few files will need to be moved. Copy all files in the `examples/` directory into the root directory and replace needed lines with your credentials, tokens, and settings. This can be done with `cp -r examples/ .`

Then, setup a python virtual environment with `python3 -m venv venv`. Enter the virtual environment by using `source venv/bin/activate`. Prerequisites can then be installed using `pip install -r requirements.txt`. Run the bot with `python3 main.py`. 

## Support
**Report new bugs [here](https://github.com/thecocohead/blucifer/issues/new/choose)**. Before reporting a bug, it's very helpful to check if the bug has already been reported to avoid creating a duplicate. All listed bugs and requested features are accessible [here](https://github.com/thecocohead/blucifer/issues). 

## Want to contribute your time? 
First of all, ***THANK YOU!!!*** This bot cannot be possible without volunteer work, technical or non-technical. 

If you'd like to contribute code to this repository, check out some bugs or requested features [here](https://github.com/thecocohead/blucifer/issues). Any listing without an assignee is fair game for the taking, just post a comment asking to be assigned the issue. Any issue with the "good first issue" tag are bugs/features with a small estimated workload, and can serve as a good way to familiarize yourself with the codebase. 