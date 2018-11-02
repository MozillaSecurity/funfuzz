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
    timeout 10 hg clone --stream https://hg.mozilla.org"$1""$2" "$3"/"$2" \
        > "$3"/"$2"_url_raw.txt 2>&1
    # Ensure that the cloning process did not create any repo directories
    rm -rf "${3:?}"/"$2"
else
    echo "$3/$2 currently exists, which it shouldn't. Exiting..."
    exit 1
fi
date
echo "Extracting the bundle filename, which is:"
awk -F"/" 'NR==1{print $NF}' "$3"/"$2"_url_raw.txt 2>&1 \
    | tee "$3"/"$2"_bundle_filename.txt
date
echo "Downloading the $2 bundle..."
if [ -x "$(command -v aria2c)" ]; then
    echo "aria2c found, using it..."
    awk 'NR==1{print $5}' "$3"/"$2"_url_raw.txt \
        | timeout 45 aria2c -x5 -l "$3"/"$2"_download_log.txt -i -
    # If the first run had stalled, the second run here completes it
    if [ -f "$3"/"$(cat "$3"/"$2"_bundle_filename.txt)".aria2 ]; then
        echo "Running aria2c a second time as the first did not complete..."
        awk 'NR==1{print $5}' "$3"/"$2"_url_raw.txt \
            | aria2c -x5 -l "$3"/"$2"_download_log_2.txt -i -
    fi
else
    echo "aria2c not found, using wget instead..."
    awk 'NR==1{print $5}' "$3"/"$2"_url_raw.txt \
        | wget -i - -o "$3"/"$2"_download_log.txt
fi
date
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
rm -f /home/ubuntu/trees/mozilla-central_*.txt  # Remove all log files
popd
# The script may or may not have permissions to return to the original directory,
# esp when this script is run as a different user, hence the "|| true"
popd || true
echo "Finished retrieving the $2 repository."
