# sys

## stausee-report.sh
### Overview
This script gathers important ZFS pool and dataset information and writes it to date-stamped report files.

### Usage
1. **Make it executable**: 
   ```bash
   chmod +x /home/caleb/repo/utils/sys/stausee-report.sh
   ```
2. **Add alias to .bashrc**: 
   ```bash
   echo 'alias stausee-report="sudo /home/caleb/repo/utils/sys/stausee-report.sh"' >> /home/caleb/.bashrc
   ```
3. **Source your bashrc** to load the alias: 
   ```bash
   source ~/.bashrc
   ```
4. **Run the script** anytime with: 
   ```bash
   stausee-report
   ```
5. **To set up as a cronjob (running every 2 days at 2 AM)**, edit root's crontab:
   ```bash
   sudo crontab -e
   ```
   Add the line:
   ```
   0 2 */2 * * /home/caleb/repo/utils/sys/stausee-report.sh
   ```

### Output
Reports are stored in `/home/caleb/reports/stausee-pool/` with date-stamped filenames (e.g., `stausee-report-2024-12-13.txt`).
Each report includes:
- Pool status and health
- All pool properties
- For each dataset:
  - Space usage and quotas
  - Compression settings
  - Cache configuration
  - Performance settings
  - Mount settings
- Current I/O statistics

Reports are retained for 365 days.

---

## smart-report.sh
### Overview
This script checks all drives and saves detailed SMART information, including PARTUUIDs for correlation with ZFS pool devices.

### Usage
1. **Make it executable**:
   ```bash
   chmod +x /home/caleb/repo/utils/sys/smart-report.sh
   ```
2. **Add alias to .bashrc**: 
   ```bash
   echo 'alias smart-report="sudo /home/caleb/repo/utils/sys/smart-report.sh"' >> ~/.bashrc
   source ~/.bashrc
   ```
3. **Run the script** anytime with:
   ```bash
   smart-report
   ```
4. **To set up as a cronjob (running every 2 days at 2 AM)**, edit root's crontab:
   ```bash
   sudo crontab -e
   ```
   Add the line:
   ```
   0 2 */2 * * /home/caleb/repo/utils/sys/smart-report.sh
   ```

### Output
Reports are stored in `/home/caleb/reports/disks/` with date-stamped filenames (e.g., `smart-report-2024-12-13.txt`).
The script will:
- Check both NVMe and SATA/SAS drives
- Include PARTUUIDs for each drive
- Include drive info, SMART health, attributes, and error logs
- Include serial numbers for easy identification
- Keep reports for 365 days