## @ingroup Components-Energy-Distributors
# HTS_DC_Dynamo_Basic.py
#
# Created:  Feb 2020,   K. Hamilton - Through New Zealand Ministry of Business Innovation and Employment Research Contract RTVU2004 
# Modified: Jan 2022,   S. Claridge

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------

# suave imports
import SUAVE
import numpy as np
from SUAVE.Components.Energy.Energy_Component import Energy_Component
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------
#  HTS DC Dynamo Class
# ----------------------------------------------------------------------

## @ingroup Components-Energy-Distributors
class HTS_DC_Dynamo_Basic(Energy_Component):
    """ Basic HTS Dynamo model for constant current DC coil operation at constant cryogenic temperature.

        Assumptions:
        HTS Dynamo is operating at rated temperature and output current.

        Source:
        None
    """

    def __defaults__(self):
        """ This sets the default values.
    
            Assumptions:
            None
    
            Source:
            N/A
    
            Inputs:
            None
    
            Outputs:
            None
    
            Properties Used:
            None
            """         
        
        self.outputs.efficiency             =   0.0      # [W/W]
        self.mass_properties.mass   =   0.0      # [kg] 
        self.rated_current           =   0.0      # [A]
        self.rated_RPM               =   0.0      # [RPM]
        self.rated_temp              =   0.0      # [K]
        self.inputs.hts_current             =   0.0      # [A]
        self.inputs.power_out               =   0.0      # [W]
        self.outputs.cryo_load              =   0.0      # [W]
        self.outputs.power_in               =   0.0      # [W]

    
    def shaft_power(self, conditions):
        """ The shaft power that must be supplied to the DC Dynamo supply to power the HTS coils.
            Assumptions:
                HTS Dynamo is operating at rated temperature.
                
            Source:
                N/A

            Inputs:
                cryo_temp           [K]
                current             [A]
                power_out           [W]

            Outputs:
                power_in            [W]
                cryo_load           [W]

            Properties Used:
                None
        """

        hts_current = self.inputs.hts_current 

        power_out   = self.inputs.power_out 

        #Adjust efficiency according to the rotor current 
        current    = np.array(hts_current)
        efficiency = self.efficiency_curve(current)

        # Create output arrays. The hts dynamo input power is assumed zero if the output power is zero, this may not be true for some dynamo configurations however the power required for zero output power will be very low.
        # Similarly, the cryo load will be zero if no dynamo effect is occuring.
        power_in = np.array(power_out/efficiency)
        power_in[power_out==0.] = 0
        
        cryo_load  = np.array(power_in - power_out)

        # Return basic results.

        self.outputs.cryo_load              =   cryo_load
        self.outputs.power_in               =   power_in

        return [power_in, cryo_load]


    def efficiency_curve(self, current):

        """ This sets the default values.

        Assumptions:
            The efficiency curve of the Dynamo is a parabola 

        Source:
            "Practical Estimation of HTS Dynamo Losses" - Kent Hamilton, Member, IEEE, Ratu Mataira-Cole, Jianzhao Geng, Chris Bumby, Dale Carnegie, and Rod Badcock, Senior Member, IEEE

        Inputs:
            current        [A]

        Outputs:
            efficiency      [W/W]

        Properties Used:
            None
        """     

        x = np.array(current)

        if np.any(x > self.rated_current * 1.8 ) or np.any(x < self.rated_current * 0.2): #Plus minus 80
            print("Current out of range")
            return 0 

        a          = ( self.efficiency ) / np.square(self.rated_current) #one point on the graph is assumed to be  (0, 2 * current), 0  = a (current ^ 2) + efficiency 
        
        efficiency = -a * (np.square( x - self.rated_current) ) +  self.efficiency # y = -a(x - current)^2 + efficieny 

        return   efficiency



