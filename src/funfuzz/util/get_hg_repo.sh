#! /bin/bash -ex

# This script downloads a bundle from Mozilla's Mercurial repositories and extracts them.
#
# Arguments: <script> <URL connector> <repository name> <absolute base dir path>
#
# Sample commands:
#
# $ bash <script> / mozilla-central /home/ubuntu/trees
# Note that mozilla-central is in https://hg.mozilla.org/mozilla-central/
#
# $ bash <script> /releases/ mozilla-beta /home/ubuntu/trees
# Note that mozilla-beta is in https://hg.mozilla.org/releases/mozilla-beta/

mkdir -p "$3"
pushd "$3"
date
# The clone process hangs quite so often, but less when downloaded standalone
if [ ! -d "$3"/"$2" ]; then
    timeout 2 hg clone --stream https://hg.mozilla.org"$1""$2" "$3"/"$2" \
        > "$3"/"$2"_url_raw.txt 2>&1
    # Ensure that the cloning process did not create any repo directories
    rm -rf "$3"/"$2"
else
    echo "$3/$2 currently exists, which it shouldn't. Exiting..."
    exit 1
fi
date
echo "Downloading the $2 bundle..."
if [ -x "$(command -v aria2c)" ]; then
    echo "aria2c found, using it..."
    awk 'NR==1{print $5}' "$3"/"$2"_url_raw.txt \
        | timeout 40 aria2c -x5 -l "$3"/"$2"_download_log.txt -i -
    echo "Running aria2c a second time just to be sure..."
    # If the first run had stalled, the second run here completes it
    # If it did not, the second gets a 2nd (may be partial) that we do not use
    # Remember to remove this potentially duped copy at the end of this script
    # esp. if we run this yet another time (and get another potential copy)
    awk 'NR==1{print $5}' "$3"/"$2"_url_raw.txt \
        | timeout 20 aria2c -x5 -l "$3"/"$2"_download_log_2.txt -i -
    awk 'NR==1{print $5}' "$3"/"$2"_url_raw.txt \
        | timeout 10 aria2c -x5 -l "$3"/"$2"_download_log_3.txt -i -
else
    echo "aria2c not found, using wget instead..."
    awk 'NR==1{print $5}' "$3"/"$2"_url_raw.txt \
        | wget -i - -o "$3"/"$2"_download_log.txt
fi
date
echo "Extracting the bundle filename minus the front and back single quotes..."
if [ -x "$(command -v aria2c)" ]; then
    grep "Download complete" "$3"/"$2"_download_log.txt \
        | awk -F"/" '{print $NF}' 2>&1 \
        | tee "$3"/"$2"_bundle_filename.txt
else
    awk 'NR==6{print substr($3, 2, length($3)-2)}' \
        "$3"/"$2"_download_log.txt 2>&1 \
        | tee "$3"/"$2"_bundle_filename.txt
fi
echo "Extracting the bundle into $3/$2..."
hg init "$3"/"$2"
pushd "$3"/"$2"
date
hg debugapplystreamclonebundle "$3"/"$(cat "$3"/"$2"_bundle_filename.txt)"
date
echo "Adding the .hgrc for the repository..."
cat << EOF > "$3"/"$2"/.hg/hgrc
[paths]

default = https://hg.mozilla.org$1$2
EOF
echo "Updating to default tip gets included below as well..."
date
hg -R "$3"/"$2" pull -u
date
rm "$3"/"$(cat "$3"/"$2"_bundle_filename.txt)"
rm -f "$3"/*.packed1.1.hg*  # Potential 2nd copy, last * deletes *.aria2 too
rm -f "$3"/*.packed1.2.hg*  # Potential 3rd copy, last * deletes *.aria2 too
popd
# The script may or may not have permissions to return to the original directory,
# esp when this script is run as a different user, hence the "|| true"
popd || true
echo "Finished retrieving the $2 repository."
