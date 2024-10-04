# Development CLI usage

Terminal will need to have access to Python.

1. Terminal: Install Prompt Toolkit
```bash
pip install prompt_toolkit
```

2. Text Editor: Edit the device model passed to `Vssl` in `cli.py`. Device models can be found [here](https://github.com/vsslctrl/vsslctrl/blob/fdaffdefa35cf4e11f05e8a7792584e597e20a04/vsslctrl/device.py#L61).
```python
...
 vssl = Vssl(DeviceModels.A1X)
...
```

3. Text Editor: Edit zones IP addresses in `cli.py` 
```python
...
 zone1 = vssl.add_zone(ZoneIDs.ZONE_1, "192.168.1.10")
 # zone2 = vssl.add_zone(ZoneIDs.ZONE_2, "192.168.1.11")
 # zone3 = vssl.add_zone(ZoneIDs.ZONE_3, "192.168.1.12")
...
```

4. Terminal: Run the program:
```bash
# Run the script
python cli.py
```

5. Terminal: Monitor script output in another terminal window
```bash
# Tail the log output from the script
tail -f vssl.log
```