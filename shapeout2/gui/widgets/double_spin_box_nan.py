import numpy as np
from PyQt6 import QtWidgets, QtGui


class DoubleSpinBoxNan(QtWidgets.QDoubleSpinBox):
    """A doubleSpinBox that uses minimum() and maximum() as np.nan"""

    def __init__(self, *args, **kwargs):
        super(DoubleSpinBoxNan, self).__init__(*args, **kwargs)
        self._suffix = self.suffix()  # remember initial suffix
        self.validator = NanFloatValidator()

    def validate(self, text, position):
        return self.validator.validate(text, position, self.suffix())

    def value(self):
        value = super(DoubleSpinBoxNan, self).value()
        if value == self.minimum() or value == self.maximum():
            value = np.nan
        return value

    def valueFromText(self, text):
        if text == "nan":
            return np.nan
        else:
            return convert_string_to_nanfloat(text[:-len(self.suffix())])

    def textFromValue(self, value):
        if value == self.minimum() or value == self.maximum():
            return "nan"
        else:
            return str(value)


class NanFloatValidator(QtGui.QValidator):
    def validate(self, text, position, suffix):
        string = text[:-len(suffix)]
        if string in ["n", "na", "nan"]:
            text = "nan"
        if valid_nanfloat_string(string):
            return self.State.Acceptable, text, position
        elif string == "":
            return self.State.Intermediate, text, position
        return self.State.Invalid, text, position

    def fixup(self, text):
        try:
            val = convert_string_to_nanfloat(text)
        except ValueError:
            val = ""
        return str(val)


def valid_nanfloat_string(string):
    try:
        convert_string_to_nanfloat(string)
    except ValueError:
        valid = False
    else:
        valid = True
    return valid


def convert_string_to_nanfloat(string):
    try:
        val = float(string)
    except ValueError:
        string = string.strip()
        for iid in ["n", "na", "nan"]:
            if string.startswith(iid):
                val = np.nan
                break
        else:
            raise ValueError("Not a valid nan-float!")
    return val
