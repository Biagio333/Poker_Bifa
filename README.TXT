per scpr che cre sempre dev

echo v4l2loopback | sudo tee -a /etc/modules
sudo nano /etc/modprobe.d/v4l2loopback.conf
#dentro scrivi:
options v4l2loopback devices=1 video_nr=0 card_label="scrcpy"