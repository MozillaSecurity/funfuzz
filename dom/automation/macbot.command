rm -rf ~/fuzzing/dom/automation/build/
ping -c 60 -o 192.168.1.2 && hg -R ~/fuzzing pull -u && cd ~/fuzzing/dom/automation && python bot.py && echo bot.py exited successfully
echo REBOOT COMING
sleep 15
sudo reboot
