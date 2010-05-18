ping -c 60 -o 192.168.1.2 && hg -R ~/fuzzing pull -u && cd ~/fuzzing/dom/automation && python bot.py && echo ABOUT TO REBOOT && sleep 3 && rm -rf build && sudo reboot
