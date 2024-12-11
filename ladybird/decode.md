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
