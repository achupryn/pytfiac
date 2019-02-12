"""Python3 library for climate device using the TFIAC protocol."""
import logging

UDP_PORT = 7777

_LOGGER = logging.getLogger(__name__)

MIN_TEMP = 61
MAX_TEMP = 88

OPERATION_LIST = ['heat', 'selfFeel', 'dehumi', 'fan', 'cool']
FAN_LIST = ['Auto', 'Low', 'Middle', 'High']
SWING_LIST = [
    'Off',
    'Vertical',
    'Horizontal',
    'Both',
]

CURR_TEMP = 'current_temp'
TARGET_TEMP = 'target_temp'
OPERATION_MODE = 'operation'
FAN_MODE = 'fan_mode'
SWING_MODE = 'swing_mode'
ON_MODE = 'is_on'

STATUS_MESSAGE = '<msg msgid="SyncStatusReq" type="Control" seq="{seq:.0f}">' \
                 '<SyncStatusReq></SyncStatusReq></msg>'
SET_MESSAGE = '<msg msgid="SetMessage" type="Control" seq="{seq:.0f}">' + \
              '<SetMessage>{message}</SetMessage></msg>'

UPDATE_MESSAGE = '<TurnOn>{{{}}}</TurnOn>'.format(ON_MODE) + \
                 '<BaseMode>{{{}}}</BaseMode>'.format(OPERATION_MODE) + \
                 '<SetTemp>{{{}}}</SetTemp>'.format(TARGET_TEMP) + \
                 '<WindSpeed>{{{}}}</WindSpeed>'.format(FAN_MODE)

SET_SWING_OFF = '<WindDirection_H>off</WindDirection_H>' \
                '<WindDirection_V>off</WindDirection_V>'
SET_SWING_3D = '<WindDirection_H>on</WindDirection_H>' \
               '<WindDirection_V>on</WindDirection_V>'
SET_SWING_VERTICAL = '<WindDirection_H>off</WindDirection_H>' \
                     '<WindDirection_V>on</WindDirection_V>'
SET_SWING_HORIZONTAL = '<WindDirection_H>on</WindDirection_H>' \
                       '<WindDirection_V>off</WindDirection_V>'

SET_SWING = {
    'Off': SET_SWING_OFF,
    'Vertical': SET_SWING_VERTICAL,
    'Horizontal': SET_SWING_HORIZONTAL,
    'Both': SET_SWING_3D,
}


class Tfiac():
    """TFIAC class to handle connections."""

    def __init__(self, host):
        """Init class."""
        self._host = host
        self._status = {}
        self._name = None
        self.update()

    @property
    def _seq(self):
        from time import time
        return time() * 1000

    def send(self, message):
        """Send message."""
        import socket
        _LOGGER.debug("Sending message: %s", message.encode())
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)  # 5 second timeout
        sock.sendto(message.encode(), (self._host, UDP_PORT))
        data = sock.recv(4096)
        sock.close()
        return data

    def update(self):
        """Update the state of the A/C."""
        import xmltodict
        _seq = self._seq
        response = self.send(STATUS_MESSAGE.format(seq=_seq))
        try:
            _status = dict(xmltodict.parse(response)['msg']['statusUpdateMsg'])
            _LOGGER.debug("Current status %s", _status)
            self._name = _status['DeviceName']
            self._status[CURR_TEMP] = float(_status['IndoorTemp'])
            self._status[TARGET_TEMP] = float(_status['SetTemp'])
            self._status[OPERATION_MODE] = _status['BaseMode']
            self._status[FAN_MODE] = _status['WindSpeed']
            self._status[ON_MODE] = _status['TurnOn']
            self._status[SWING_MODE] = self._map_winddirection(_status)
        except Exception as ex:  # pylint: disable=W0703
            _LOGGER.error(ex)

    def _map_winddirection(self, _status):
        """Map WindDirection to swing_mode."""
        value = 0
        if _status['WindDirection_H'] == 'on':
            value = 1
        if _status['WindDirection_V'] == 'on':
            value |= 2
        return {0: 'Off', 1: 'Horizontal', 2: 'Vertical', 3: 'Both'}[value]

    def set_state(self, mode, value):
        """Set the new state of the ac."""
        self.update()  # make sure we have the latest settings.
        self._status.update({mode: value})
        self.send(
            SET_MESSAGE.format(seq=self._seq,
                               message=UPDATE_MESSAGE).format(**self._status))

    def set_swing(self, value):
        """Set swing mode."""
        self.send(
            SET_MESSAGE.format(seq=self._seq, message=SET_SWING[value])
        )

    @property
    def name(self):
        """Return name of device."""
        return self._name

    @property
    def status(self):
        """Return dict of current status."""
        return self._status