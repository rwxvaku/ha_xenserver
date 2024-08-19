# ha_xenserver
XenServer Integration for Home Assistant

### Features
- [x] Switch for Every VM.
- [ ] Monitoring Data.
- [ ] Console.

### Usage
#### Installation

```bash
# login into HA Terminal
cd config
mkdir custom_components
cd custom_components
git clone https://github.com/rwxvaku/ha_xenserver
mv ha_xenserver test_hello
```

#### Activating
* Browse to your Home Assistant instance.
* Go to Settings > Devices & Services.
* In the bottom right corner, select the Add Integration button.
* From the list, select test_hello.
* Follow the instructions on screen to complete the setup.