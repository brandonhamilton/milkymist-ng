from migen.fhdl.std import *
from migen.genlib.cdc import MultiReg
from migen.bank.description import *

class Clocking(Module, AutoCSR):
	def __init__(self, pads):
		self._r_pll_reset = CSRStorage(reset=1)
		self._r_locked = CSRStatus()

		# DRP
		self._r_pll_adr = CSRStorage(5)
		self._r_pll_dat_r = CSRStatus(16)
		self._r_pll_dat_w = CSRStorage(16)
		self._r_pll_read = CSR()
		self._r_pll_write = CSR()
		self._r_pll_drdy = CSRStatus()

		self.locked = Signal()
		self.serdesstrobe = Signal()
		self.clock_domains._cd_pix = ClockDomain()
		self.clock_domains._cd_pix2x = ClockDomain()
		self.clock_domains._cd_pix10x = ClockDomain(reset_less=True)

		###

		clk_se = Signal()
		self.specials += Instance("IBUFDS", i_I=pads.clk_p, i_IB=pads.clk_n, o_O=clk_se)

		clkfbout = Signal()
		pll_locked = Signal()
		pll_clk0 = Signal()
		pll_clk1 = Signal()
		pll_clk2 = Signal()
		pll_drdy = Signal()
		self.sync += If(self._r_pll_read.re | self._r_pll_write.re,
			self._r_pll_drdy.status.eq(0)
		).Elif(pll_drdy,
			self._r_pll_drdy.status.eq(1)
		)
		self.specials += Instance("PLL_ADV",
			p_CLKFBOUT_MULT=10,
			p_CLKOUT0_DIVIDE=1,  # pix10x
			p_CLKOUT1_DIVIDE=5,  # pix2x
			p_CLKOUT2_DIVIDE=10, # pix
			p_COMPENSATION="INTERNAL",
			
			i_CLKINSEL=1,
			i_CLKIN1=clk_se,
			o_CLKOUT0=pll_clk0, o_CLKOUT1=pll_clk1, o_CLKOUT2=pll_clk2,
			o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbout,
			o_LOCKED=pll_locked, i_RST=self._r_pll_reset.storage,

			i_DADDR=self._r_pll_adr.storage,
			o_DO=self._r_pll_dat_r.status,
			i_DI=self._r_pll_dat_w.storage,
			i_DEN=self._r_pll_read.re | self._r_pll_write.re,
			i_DWE=self._r_pll_write.re,
			o_DRDY=pll_drdy,
			i_DCLK=ClockSignal())

		locked_async = Signal()
		self.specials += [
			Instance("BUFPLL", p_DIVIDE=5,
				i_PLLIN=pll_clk0, i_GCLK=ClockSignal("pix2x"), i_LOCKED=pll_locked,
				o_IOCLK=self._cd_pix10x.clk, o_LOCK=locked_async, o_SERDESSTROBE=self.serdesstrobe),
			Instance("BUFG", i_I=pll_clk1, o_O=self._cd_pix2x.clk),
			Instance("BUFG", i_I=pll_clk2, o_O=self._cd_pix.clk),
			MultiReg(locked_async, self.locked, "sys")
		]
		self.comb += self._r_locked.status.eq(self.locked)

		# sychronize pix+pix2x reset
		pix_rst_n = 1
		for i in range(2):
			new_pix_rst_n = Signal()
			self.specials += Instance("FDCE", i_D=pix_rst_n, i_CE=1, i_C=ClockSignal("pix"),
				i_CLR=~locked_async, o_Q=new_pix_rst_n)
			pix_rst_n = new_pix_rst_n
		self.comb += self._cd_pix.rst.eq(~pix_rst_n), self._cd_pix2x.rst.eq(~pix_rst_n)
