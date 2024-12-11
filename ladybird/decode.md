get the tiled streams from the first tenth-second clip
```bash
ffmpeg -i 0.ts -map 0:v:0 -c copy tile_top_left.hevc
ffmpeg -i 0.ts -map 0:v:1 -c copy tile_top_right.hevc
ffmpeg -i 0.ts -map 0:v:2 -c copy tile_bottom_left.hevc
ffmpeg -i 0.ts -map 0:v:3 -c copy tile_bottom_right.hevc
```
try to tile them together
```bash
ffmpeg \
-i tile_top_left.hevc \
-i tile_top_right.hevc \
-i tile_bottom_left.hevc \
-i tile_bottom_right.hevc \
-filter_complex "[0:v][1:v]hstack=inputs=2[top];[2:v][3:v]hstack=inputs=2[bottom];[top][bottom]vstack=inputs=2" \
-c:v libx264 -crf 18 -preset slow output_full_frame.mp4
```
let's move these somewhere else:
```bash
mv tile_top_left.hevc ~/ladybird_failed_copy/misc
mv tile_top_right.hevc ~/ladybird_failed_copy/misc
mv tile_bottom_left.hevc ~/ladybird_failed_copy/misc
mv tile_bottom_right.hevc ~/ladybird_failed_copy/misc
mv output_full_frame.mp4 ~/ladybird_failed_copy/misc
```

determine the pixel overlap:
```bash
# blade
cd /home/caleb/ladybird_failed_copy/0H/0M/0S
ffmpeg -y -i 0.ts -map 0:v:0 -frames:v 1 -pix_fmt rgb24 /home/caleb/ladybird_failed_copy/inspect_tiles/top_left.png
ffmpeg -y -i 0.ts -map 0:v:1 -frames:v 1 -pix_fmt rgb24 /home/caleb/ladybird_failed_copy/inspect_tiles/top_right.png
ffmpeg -y -i 0.ts -map 0:v:2 -frames:v 1 -pix_fmt rgb24 /home/caleb/ladybird_failed_copy/inspect_tiles/bottom_left.png
ffmpeg -y -i 0.ts -map 0:v:3 -frames:v 1 -pix_fmt rgb24 /home/caleb/ladybird_failed_copy/inspect_tiles/bottom_right.png
```
```bash
# wsl
rsync -avz caleb@blade:/home/caleb/ladybird_failed_copy/inspect_tiles/ ~/ladybird_failed_copy/inspect_tiles
```
test the overlap:
```bash
ffmpeg -i top_left.png -i top_right.png -i bottom_left.png -i bottom_right.png \
  -filter_complex "\
    [0:v]crop=iw-32:ih-32:0:0[tl];\
    [1:v]crop=iw-32:ih-32:32:0[tr];\
    [2:v]crop=iw-32:ih-32:0:32[bl];\
    [3:v]crop=iw-32:ih-32:32:32[br];\
    [tl][tr]hstack=2[top];\
    [bl][br]hstack=2[bottom];\
    [top][bottom]vstack=2" \
  test_stitch.png
```
*hypothesis confirmed!*


Tile Layout & Overlap Structure:
- Each frame is divided into a 2x2 grid of tiles
- Adjacent tiles overlap by 64 pixels
- To correct this, we crop 32px from each overlapping edge:
  * top-left:     crop 32px from right and bottom edges
  * top-right:    crop 32px from left and bottom edges
  * bottom-left:  crop 32px from top and right edges
  * bottom-right: crop 32px from top and left edges
