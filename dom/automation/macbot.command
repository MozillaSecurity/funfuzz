ping -c 60 -o 192.168.1.2 && hg -R ~/fuzzing pull -u && rm -rf ~/fuzzing/dom/automation/build/
cd ~/fuzzing/dom/automation && python bot.py && echo bot.py exited successfully
echo REBOOT COMING
sleep 15
sudo reboot
