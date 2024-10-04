# Development CLI usage

Terminal will need to have access to Python.

1. Install Prompt Toolkit
```bash
pip install prompt_toolkit
```

2. Edit the device model passed to `Vssl` in `cli.py` (e.g `vssl = Vssl(DeviceModels.A3X)`). Models can be found [here](https://github.com/vsslctrl/vsslctrl/blob/fdaffdefa35cf4e11f05e8a7792584e597e20a04/vsslctrl/device.py#L61)
3. Edit zones IP addresses in `cli.py` 

4. Run the program:
```bash
# Run the script
python cli.py
```

5. Monitor script output in another terminal window
```bash
# Tail the log output from the script
tail -f vssl.log
```