sleep 10 && ping -c 1 -o www.mozilla.org && hg -R ~/fuzzing pull -u
python fuzzing/dom/automation/bot.py
echo REBOOT COMING
sleep 15
sudo reboot
