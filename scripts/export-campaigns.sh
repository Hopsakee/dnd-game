#!/usr/bin/env bash
# Copy the campaign database out of the running container into the transport
# folder, so Hoggle can read the play-test flags. Run on the Mac, from anywhere:
#
#   ~/dnd-game/scripts/export-campaigns.sh            # to ~/Drive/HoggleTransport/dndgame
#   ~/dnd-game/scripts/export-campaigns.sh some/dir   # elsewhere
#
# The copy is made with SQLite's backup inside the container, so it is
# consistent even while a turn is being saved; copying the live file could
# catch it half-written. Each export gets the date and time in its name.
set -euo pipefail

dest_dir="${1:-$HOME/Drive/HoggleTransport/dndgame}"
dest="$dest_dir/campaigns-$(date +%Y-%m-%d-%H%M).db"
tmp=/tmp/campaigns-export.db

cd "$(dirname "$0")/.."   # compose.yaml lives here
mkdir -p "$dest_dir"
docker compose exec -T solo-dm python -c "
import sqlite3
src = sqlite3.connect('file:/app/campaigns/campaigns.db?mode=ro', uri=True)
dst = sqlite3.connect('$tmp')
src.backup(dst)
dst.close()
"
docker compose cp "solo-dm:$tmp" "$dest"
docker compose exec -T solo-dm rm -f "$tmp"
echo "Exported to $dest"
