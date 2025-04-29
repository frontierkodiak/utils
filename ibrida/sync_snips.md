# sync pta dataset (center-cropped, non-localized) to carbon
## labels
```bash
rsync /peach/generated/v0/r1/pta_all_exc_nonrg_sp_inc_oor_fas_elev/labels.h5 carbon@carbon:/Users/carbon/Data/ibrida/v0r1/labels/pta_all_exc_nonrg_sp_inc_oor_fas_elev/labels.h5
```
## images
```bash
rclone copy \
  blade:/general/generated/v0/r1/pta/images/384p_60q/ \
  /Users/carbon/Data/ibrida/v0r1/images/non_localized/pta_full/ \
  --transfers=16 \
  --checkers=16 \
  --progress \
  --log-level INFO
```
