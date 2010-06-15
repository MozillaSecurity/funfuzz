sleep 10 && ping -c 1 -o www.mozilla.org && hg -R ~/fuzzing pull -u && rm -rf ~/fuzzing/dom/automation/build/
cd ~/fuzzing/dom/automation && python bot.py && echo bot.py exited successfully
echo REBOOT COMING
sleep 15
sudo reboot
