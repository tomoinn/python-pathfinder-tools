from fpdf import FPDF


class TransparentPDF(FPDF):
    """
    Extension of FPDF class to allow for PDF1.4 transparency in the graphics state
    """

    def __init__(self, orientation, unit, format):
        super(TransparentPDF, self).__init__(orientation=orientation, unit=unit, format=format)
        self.extgstates = {}

    def set_alpha(self, alpha, bm='Normal'):
        """
        Set the current transparency used for drawing operations
        :param alpha:
            Alpha value, 0.0 to 1.0
        :param bm:
            Blend mode, defaults to Normal
        """
        gs = self.add_ext_gstate({'ca': alpha, 'CA': alpha, 'BM': bm})
        self._set_ext_gstate(gs)

    def set_fill_with_alpha(self, red, green, blue, alpha=None):
        if alpha is not None:
            self.set_alpha(alpha)
        self.set_fill_color(red, green, blue)

    def add_ext_gstate(self, parms):
        n = len(self.extgstates.keys()) + 1
        if n not in self.extgstates.keys():
            self.extgstates[n] = {'parms': parms}
        else:
            self.extgstates[n]['parms'] = parms
        return n

    def _set_ext_gstate(self, gs):
        self._out(f'/GS{gs} gs')

    def _enddoc(self):
        # Transparency only supported with PDF version >= 1.4
        if self.extgstates and self.pdf_version < '1.4':
            self.pdf_version = '1.4'
        super()._enddoc()

    def _putextgstates(self):
        for key, state in self.extgstates.items():
            self._newobj()
            state['n'] = self.n
            self._out('<</Type /ExtGState')
            parms = state['parms']
            self._out(f'/ca {parms["ca"]}')
            self._out(f'/CA {parms["CA"]}')
            self._out(f'/BM/{parms["BM"]}')
            self._out('>>endobj')
            # self._out('endobj')

    def _putresources(self):
        # Add resources to the PDF object
        self._putextgstates()
        super()._putresources()

    def _putresourcedict(self):
        # Add external graphics states to resource dictionary
        super()._putresourcedict()
        self._out('/ExtGState <<')
        for key, state in self.extgstates.items():
            self._out(f'/GS{str(key)} {state["n"]} 0 R')
        self._out('>>')
