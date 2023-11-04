class InputError(Exception):
    def __int__(self, piece=None):
        self._piece = piece
    def __str__(self):
        if self._piece is not None:
            return "The field %s contains an incorrect value!"%self._piece
        return "You provided incorrect input!"