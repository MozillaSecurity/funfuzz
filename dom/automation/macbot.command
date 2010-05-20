ping -c 60 -o 192.168.1.2 && hg -R ~/fuzzing pull -u && cd ~/fuzzing/dom/automation && python bot.py && echo bot.py exited successfully && sleep 3 && rm -rf build
echo REBOOT COMING
sleep 10
sudo reboot
