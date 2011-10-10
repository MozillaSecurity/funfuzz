date

sleep 10 && ping -c 1 -o www.mozilla.org && hg -R ~/fuzzing pull -u

python fuzzing/dom/automation/bot.py

# Reboot in a way that ensures the terminal window won't be saved
echo REBOOT COMING
sleep 8
bash -c "sleep 4 && /usr/bin/osascript fuzzing/dom/automation/mac-close-terminal.applescript.txt && sleep 4 && sudo reboot" &
