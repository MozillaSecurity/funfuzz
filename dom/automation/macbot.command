date

sleep 10 && ping -c 1 -o www.mozilla.org && hg -R ~/funfuzz pull -u

python funfuzz/dom/automation/bot.py --test-type=dom --target-time=43200

# Reboot in a way that ensures the terminal window won't be saved
echo REBOOT COMING
sleep 8
bash -c "sleep 4 && /usr/bin/osascript funfuzz/dom/automation/mac-close-terminal.applescript.txt && sleep 4 && sudo reboot" &
