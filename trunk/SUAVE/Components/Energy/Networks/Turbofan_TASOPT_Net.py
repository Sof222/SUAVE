#Turbofan_Network.py
# 
# Created:  Anil Variyar, Feb 2016
# Modified:  

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------

# suave imports
import SUAVE

# package imports
import numpy as np
import scipy as sp
import datetime
import time
from SUAVE.Core import Units


# python imports
import os, sys, shutil
from copy import deepcopy
from warnings import warn
import copy


from SUAVE.Core import Data, Data_Exception, Data_Warning
from SUAVE.Components import Component, Physical_Component, Lofted_Body
from SUAVE.Components.Propulsors.Propulsor import Propulsor


# ----------------------------------------------------------------------
#  Turbofan Network
# ----------------------------------------------------------------------

class Turbofan_TASOPT_Net(Propulsor):
    
    def __defaults__(self):
        
        #setting the default values
        self.tag = 'Turbo_Fan'
        self.number_of_engines = 1.0
        self.nacelle_diameter  = 1.0
        self.engine_length     = 1.0
        self.bypass_ratio      = 1.0   
        
        self.design_params     = None
        self.offdesign_params  = None
        self.max_iters         = 80 #1
        self.newton_relaxation = 1.0 
        self.compressor_map_file = "Compressor_map.txt"
        self.cooling_flow = 1
        self.no_of_turbine_stages = 1
    
    
    _component_root_map = None
        
    
    def unpack(self):

        self.design_params    = Data()
        self.offdesign_params = Data()

        dp    = self.design_params       
        
        
        #design parameters---------------------------------------
        
        dp.aalpha  = self.bypass_ratio     
        
        dp.pi_d    = self.inlet_nozzle.pressure_ratio
        dp.eta_d   = self.inlet_nozzle.polytropic_efficiency
        
        dp.pi_f    = self.fan.pressure_ratio
        dp.eta_f   = self.fan.polytropic_efficiency
        
        dp.pi_fn   = self.fan_nozzle.pressure_ratio
        dp.eta_fn  = self.fan_nozzle.polytropic_efficiency
        
        dp.pi_lc   = self.low_pressure_compressor.pressure_ratio
        dp.eta_lc  = self.low_pressure_compressor.polytropic_efficiency
        
        dp.pi_hc   = self.high_pressure_compressor.pressure_ratio
        dp.eta_hc  = self.high_pressure_compressor.polytropic_efficiency
        
        dp.Tt4     = self.combustor.turbine_inlet_temperature
        dp.pi_b    = self.combustor.pressure_ratio 
        dp.eta_b   = self.combustor.efficiency
        dp.htf     = self.combustor.fuel_data.specific_energy 
        
        dp.eta_lt  = self.low_pressure_turbine.polytropic_efficiency
        dp.etam_lt = self.low_pressure_turbine.mechanical_efficiency
        
        dp.eta_ht  = self.high_pressure_turbine.polytropic_efficiency
        dp.etam_ht = self.high_pressure_turbine.mechanical_efficiency
        
        dp.pi_tn   = self.core_nozzle.pressure_ratio
        dp.eta_tn  = self.core_nozzle.polytropic_efficiency
        
        
        dp.Pt5     = 1.0
        dp.M2      = 0.6
        dp.M2_5    = 0.6
        
        dp.HTR_f   = self.fan.hub_to_tip_ratio
        dp.HTR_hc  = self.high_pressure_compressor.hub_to_tip_ratio
                  
        dp.Tref    = 288.15
        dp.Pref    = 101325.0
        
        dp.GF      = 1.0
        dp.Tt4_spec = np.copy(dp.Tt4) #1680.
        dp.N_spec   = 1.0
        dp.Tt4_Tt2  = 1.0
        
        #offdesign parameters---------------------------------------
        
        odp = copy.deepcopy(dp)
        self.offdesign_params = odp

    

    def evaluate(self,conditions,flag,dp_eval = None):

        #Unpack
        
        if dp_eval:
            dp = dp_eval
        else:
            dp = self.offdesign_params
        
        
        #if abs(dp.pi_f-1.68)>.1:
            #aaa = 0
        
        P0 = conditions.freestream.pressure.T
        T0 = conditions.freestream.temperature.T
        M0  = conditions.freestream.mach_number.T
        gamma = 1.4
        Cp    = 1.4*287.87/(1.4-1)
        R     = 287.87
        g     = 9.81
        throttle = conditions.propulsion.throttle
        N_spec  = throttle.T
        dp.N_spec = throttle.T
        results = Data()                            

        # Ram calculations
        a0 = np.sqrt(gamma*R*T0)
        u0 = M0*a0
        Dh = .5*u0*u0
        h0  = Cp*T0
        
        ram = self.ram        
        ram.inputs.total_temperature = T0
        ram.inputs.total_pressure    = P0
        ram.inputs.total_enthalpy    = h0
        ram.inputs.delta_enthalpy    = Dh
        ram.inputs.working_fluid.specific_heat     = Cp
        ram.inputs.working_fluid.gamma             = gamma
        ram.compute_flow()
        
        Tt0 = ram.outputs.total_temperature
        Pt0 = ram.outputs.total_pressure
        ht0 = ram.outputs.total_enthalpy
        
        
        # Inlet Nozzle (stages 1.8 and 1.9 are assumed to match)

        inlet_nozzle = self.inlet_nozzle
        inlet_nozzle.inputs.total_temperature = Tt0
        inlet_nozzle.inputs.total_pressure    = Pt0
        inlet_nozzle.inputs.total_enthalpy    = ht0
        inlet_nozzle.compute_flow()
        
        Tt2 = inlet_nozzle.outputs.total_temperature
        Pt2 = inlet_nozzle.outputs.total_pressure
        ht2 = inlet_nozzle.outputs.total_enthalpy
        
        Tt1_9 = Tt2 # These are needed for other calculations
        Pt1_9 = Pt2 
        ht1_9 = ht2 
        
        
        # Fan
        
        if flag == 0:
            design_run = True
        else:
            design_run = False
        fan = self.fan
        
        if design_run:
            fan.set_design_condition()
        else:
            fan.corrected_mass_flow   = dp.mf
            fan.pressure_ratio        = dp.pi_f
            fan.compute_performance()
            dp.eta_f = fan.polytropic_efficiency
            Nfn      = fan.corrected_speed
            dNfn_pif = fan.speed_change_by_pressure_ratio
            dNfn_mf  = fan.speed_change_by_mass_flow
            
        fan.inputs.working_fluid.specific_heat = Cp
        fan.inputs.working_fluid.gamma         = gamma
        fan.inputs.working_fluid.R             = R
        fan.inputs.total_temperature           = Tt2
        fan.inputs.total_pressure              = Pt2
        fan.inputs.total_enthalpy              = ht2
        fan.compute()
        
        Tt2_1 = fan.outputs.total_temperature
        Pt2_1 = fan.outputs.total_pressure
        ht2_1 = fan.outputs.total_enthalpy
        
        
        # Fan Nozzle
        
        fan_nozzle = self.fan_nozzle
        fan_nozzle.inputs.working_fluid.specific_heat = Cp
        fan_nozzle.inputs.working_fluid.gamma         = gamma
        fan_nozzle.inputs.working_fluid.R             = R        
        fan_nozzle.inputs.total_temperature = Tt2_1
        fan_nozzle.inputs.total_pressure    = Pt2_1
        fan_nozzle.inputs.total_enthalpy    = ht2_1

        fan_nozzle.compute()
        
        Tt7 = fan_nozzle.outputs.total_temperature
        Pt7 = fan_nozzle.outputs.total_pressure
        ht7 = fan_nozzle.outputs.total_enthalpy
        
        # Original code - differs from TASOPT manual
        Pt7 = Pt2_1*dp.pi_fn
        Tt7 = Tt2_1*dp.pi_fn**((gamma-1.)*dp.eta_fn/(gamma))
        ht7 = Cp*Tt7


        # Low Pressure Compressor

        lpc = self.low_pressure_compressor
        if design_run:
            lpc.set_design_condition()
        else:
            lpc.corrected_mass_flow   = dp.mlc
            lpc.pressure_ratio        = dp.pi_lc
            lpc.compute_performance()
            dp.eta_lc = lpc.polytropic_efficiency
            Nln       = lpc.corrected_speed
            dNln_pilc = lpc.speed_change_by_pressure_ratio
            dNln_mlc  = lpc.speed_change_by_mass_flow
            
        lpc.inputs.working_fluid.specific_heat = Cp
        lpc.inputs.working_fluid.gamma         = gamma
        lpc.inputs.working_fluid.R             = R
        lpc.inputs.total_temperature           = Tt2
        lpc.inputs.total_pressure              = Pt2
        lpc.inputs.total_enthalpy              = ht2
        lpc.compute()
        
        Tt2_5 = lpc.outputs.total_temperature
        Pt2_5 = lpc.outputs.total_pressure
        ht2_5 = lpc.outputs.total_enthalpy

        
        # High Pressure Compressor
        
        hpc = self.high_pressure_compressor
        if design_run:
            hpc.set_design_condition()
        else:
            hpc.corrected_mass_flow   = dp.mhc
            hpc.pressure_ratio        = dp.pi_hc
            hpc.compute_performance()
            dp.eta_hc = hpc.polytropic_efficiency
            Nhn       = hpc.corrected_speed
            dNhn_pihc = hpc.speed_change_by_pressure_ratio
            dNhn_mhc  = hpc.speed_change_by_mass_flow
            
        hpc.inputs.working_fluid.specific_heat = Cp
        hpc.inputs.working_fluid.gamma         = gamma
        hpc.inputs.working_fluid.R             = R
        hpc.inputs.total_temperature           = Tt2_5
        hpc.inputs.total_pressure              = Pt2_5
        hpc.inputs.total_enthalpy              = ht2_5
        hpc.compute()
        
        Tt3 = hpc.outputs.total_temperature
        Pt3 = hpc.outputs.total_pressure
        ht3 = hpc.outputs.total_enthalpy        
   
   
        # Combustor
        
        # Some inputs are only used if a cooling combustor is used    
        combustor = self.combustor
        combustor.inputs.working_fluid.specific_heat = Cp
        combustor.inputs.working_fluid.gamma         = gamma
        combustor.inputs.working_fluid.R             = R
        combustor.inputs.total_temperature           = Tt3
        combustor.inputs.total_pressure              = Pt3
        combustor.inputs.total_enthalpy              = ht3
        
        combustor.turbine_inlet_temperature = dp.Tt4
        
        combustor.compute()
        
        Tt4 = combustor.outputs.total_temperature
        Pt4 = combustor.outputs.total_pressure
        ht4 = combustor.outputs.total_enthalpy
        f   = combustor.outputs.normalized_fuel_flow
        
        Tt4_1 = Tt4
        Pt4_1 = Pt4
        ht4_1 = ht4
        
        
        # Update the bypass ratio
        
        if design_run == False:
            mcore = dp.mlc*(Pt2/dp.Pref)/np.sqrt(Tt2/dp.Tref)/(1.0 + f)
            mfan  = dp.mf*(Pt2/dp.Pref)/np.sqrt(Tt2/dp.Tref)/(1.0 + f)
            dp.aalpha = mfan/mcore
            
            
        # High Pressure Turbine
        
        deltah_ht = -1./(1.+f)*1./dp.etam_ht*(ht3-ht2_5)
        
        hpt = self.high_pressure_turbine
        
        hpt.inputs.working_fluid.specific_heat = Cp
        hpt.inputs.working_fluid.gamma         = gamma
        hpt.inputs.total_temperature           = Tt4_1
        hpt.inputs.total_pressure              = Pt4_1
        hpt.inputs.total_enthalpy              = ht4_1
        hpt.inputs.delta_enthalpy              = deltah_ht
        
        hpt.compute()
        
        Tt4_5 = hpt.outputs.total_temperature
        Pt4_5 = hpt.outputs.total_pressure
        ht4_5 = hpt.outputs.total_enthalpy
        
        
        # Low Pressure Turbine
            
        if design_run == True:
            
            deltah_lt =  -1./(1.+f)*1./dp.etam_lt*((ht2_5 - ht1_9)+ dp.aalpha*(ht2_1 - ht2)) 
            
            lpt = self.low_pressure_turbine
            
            lpt.inputs.working_fluid.specific_heat = Cp
            lpt.inputs.working_fluid.gamma         = gamma
            lpt.inputs.total_temperature           = Tt4_5
            lpt.inputs.total_pressure              = Pt4_5
            lpt.inputs.total_enthalpy              = ht4_5
            lpt.inputs.delta_enthalpy              = deltah_lt
            
            lpt.compute()
            
            Tt4_9 = lpt.outputs.total_temperature
            Pt4_9 = lpt.outputs.total_pressure
            ht4_9 = lpt.outputs.total_enthalpy
            
        else:
            
            # Low pressure turbine off design case
            # A different setup is used for convergence per the TASOPT manual
            
            pi_lt = 1.0/dp.pi_tn*(dp.Pt5/Pt4_5)
            Pt4_9 = Pt4_5*pi_lt
            Tt4_9 = Tt4_5*pi_lt**((gamma-1.)*dp.eta_lt/(gamma))
            ht4_9 = Cp*Tt4_9 
        
        
        # Core Nozzle
        # Sometimes tn is used for turbine nozzle
        
        core_nozzle = self.core_nozzle
        core_nozzle.inputs.working_fluid.specific_heat = Cp
        core_nozzle.inputs.working_fluid.gamma         = gamma
        core_nozzle.inputs.working_fluid.R             = R        
        core_nozzle.inputs.total_temperature = Tt4_9
        core_nozzle.inputs.total_pressure    = Pt4_9
        core_nozzle.inputs.total_enthalpy    = ht4_9
    
        core_nozzle.compute()
    
        Tt5 = core_nozzle.outputs.total_temperature
        Pt5 = core_nozzle.outputs.total_pressure
        ht5 = core_nozzle.outputs.total_enthalpy    
            
            
        # Core Exhaust
        
        # set pressure ratio to atmospheric
        
        core_exhaust = self.core_exhaust
        core_exhaust.pressure_ratio = P0/Pt5
        core_exhaust.inputs.working_fluid.specific_heat = Cp
        core_exhaust.inputs.working_fluid.gamma         = gamma
        core_exhaust.inputs.working_fluid.R             = R        
        core_exhaust.inputs.total_temperature = Tt5
        core_exhaust.inputs.total_pressure    = Pt5
        core_exhaust.inputs.total_enthalpy    = ht5
        
        core_exhaust.compute()
        
        T6 = core_exhaust.outputs.static_temperature
        u6 = core_exhaust.outputs.flow_speed
        
        
        # Fan Exhaust
        
        fan_exhaust = self.fan_exhaust
        fan_exhaust.pressure_ratio = P0/Pt7
        fan_exhaust.inputs.working_fluid.specific_heat = Cp
        fan_exhaust.inputs.working_fluid.gamma         = gamma
        fan_exhaust.inputs.working_fluid.R             = R        
        fan_exhaust.inputs.total_temperature = Tt7
        fan_exhaust.inputs.total_pressure    = Pt7
        fan_exhaust.inputs.total_enthalpy    = ht7
    
        fan_exhaust.compute()
    
        T8 = fan_exhaust.outputs.static_temperature
        u8 = fan_exhaust.outputs.flow_speed              
            

        # Calculate Specific Thrust
        
        thrust = self.thrust
        thrust.inputs.normalized_fuel_flow_rate = f
        thrust.inputs.core_exhaust_flow_speed   = u6
        thrust.inputs.fan_exhaust_flow_speed    = u8
        thrust.inputs.bypass_ratio              = dp.aalpha
        
        conditions.freestream.speed_of_sound = a0
        conditions.freestream.velocity       = u0
        thrust.compute(conditions)
        
        Fsp = thrust.outputs.specific_thrust
        Isp = thrust.outputs.specific_impulse
        sfc = thrust.outputs.specific_fuel_consumption      
            
        if design_run == True:
            
            # run sizing analysis
            FD = self.thrust.total_design/(self.number_of_engines)

            # Core Mass Flow Calculation
            
            mdot_core = FD/(Fsp*a0*(1.+dp.aalpha))    
            
            
            # Fan Sizing
            
            fan.size(mdot_core,dp.M2,dp.aalpha,dp.HTR_f)
            A2 = fan.entrance_area
            
            
            # High Pressure Compressor Sizing
            
            hpc.size(mdot_core,dp.M2,dp.aalpha,dp.HTR_hc)
            A2_5 = hpc.entrance_area                      
            
            
            # Fan Nozzle Area
            
            # Remove after network is complete and above is changed to TASOPT standard
            fan_nozzle.outputs.total_temperature = Tt7
            fan_nozzle.outputs.total_enthalpy    = ht7
            
            fan_nozzle.size(mdot_core,u8,T8,P0,dp.aalpha)
            A7 = fan_nozzle.exit_area
            
            
            # Core Nozzle Area
            
            core_nozzle.size(mdot_core,u6,T6,P0)
            A5 = core_nozzle.exit_area        
            
            
            #spool speed
            
            NlcD = 1.0
            NhcD = 1.0
            
            #non dimensionalization
            
            NlD = NlcD*1.0/np.sqrt(Tt1_9/dp.Tref)
            NhD = NhcD*1.0/np.sqrt(Tt2_5/dp.Tref)
            
            mhtD = (1.0+f)*mdot_core*np.sqrt(Tt4_1/dp.Tref)/(Pt4_1/dp.Pref)
            mltD = (1.0+f)*mdot_core*np.sqrt(Tt4_5/dp.Tref)/(Pt4_5/dp.Pref)
            
            mhcD = (1.0+f)*mdot_core*np.sqrt(Tt2_5/dp.Tref)/(Pt2_5/dp.Pref)
            mlcD = (1.0+f)*mdot_core*np.sqrt(Tt2/dp.Tref)/(Pt2/dp.Pref) 
            mfD  = (1.0+f)*dp.aalpha*mdot_core*np.sqrt(Tt2/dp.Tref)/(Pt2/dp.Pref)    
            
            
            dpp = self.design_params
            
            dpp.A5   = A5
            dpp.A7   = A7
            dpp.A2   = A2
            dpp.A2_5 = A2_5
            
            
            dpp.mhtD = mhtD
            dpp.mltD = mltD
            
            dpp.mhcD = mhcD
            dpp.mlcD = mlcD
            dpp.mfD  = mfD
            fan.speed_map.design_mass_flow      = mfD
            fan.efficiency_map.design_mass_flow = mfD
            lpc.speed_map.design_mass_flow      = mlcD
            lpc.efficiency_map.design_mass_flow = mlcD
            hpc.speed_map.design_mass_flow      = mhcD
            hpc.efficiency_map.design_mass_flow = mhcD
            
            
            dpp.NlcD = NlcD
            dpp.NhcD = NhcD
            dpp.NlD  = NlD
            dpp.NhD  = NhD
            
            
            dpp.mhtD = mhtD
            dpp.mltD = mltD
            
            
            #update the offdesign params
            dpp.mhc = mhcD
            dpp.mlc = mlcD
            dpp.mf  = mfD
            
            dpp.Nl = NlcD
            dpp.Nh = NhcD
            dpp.Nf  = 1.0
            
            dpp.Nln  = NlD
            dpp.Nhn  = NhD  
            dpp.Nfn  = NlD
            fan.speed_map.Nd   = NlD
            lpc.speed_map.Nd   = NlD
            hpc.speed_map.Nd   = NhD
            
            dpp.Pt5  = Pt5
            dpp.Tt4_Tt2 = dp.Tt4/Tt2
            
            #print
            
            
            
            
            
            
            
        else:
            
            dp.Tt3 = Tt3
            dp.Pt3 = Pt3
            ##lpc
            dp.Nl = np.sqrt(Tt2/dp.Tref)*Nln
            
            ##hpc
            dp.Nh = np.sqrt(Tt2_5/dp.Tref)*Nhn
            
            ##fpc           
            dp.Nf = np.sqrt(Tt1_9/dp.Tref)*Nfn
            
                            
            dp.Tt4_spec = dp.Tt4_Tt2*Tt2*(throttle)        
            

            mdot_core = dp.mlc*Pt2/dp.Pref/np.sqrt(Tt2/dp.Tref)
            
            thrust.inputs.normalized_fuel_flow_rate = f
            thrust.inputs.core_exhaust_flow_speed   = u6
            thrust.inputs.fan_exhaust_flow_speed    = u8
            thrust.inputs.bypass_ratio              = dp.aalpha
        
            conditions.freestream.speed_of_sound = a0
            conditions.freestream.velocity       = u0
            thrust.compute(conditions)
        
            Fsp = thrust.outputs.specific_thrust
            Isp = thrust.outputs.specific_impulse
            sfc = thrust.outputs.specific_fuel_consumption            
            
            F    = Fsp*(1+dp.aalpha)*mdot_core*a0  
            mdot = mdot_core*f
            
            dp.mdot_core = mdot_core
            
            
            # Fan nozzle flow properties
            
            # Remove after network is complete and above is changed to TASOPT standard
            fan_nozzle.outputs.total_temperature = Tt7
            fan_nozzle.outputs.total_enthalpy    = ht7            
            
            fan_nozzle.compute_static(u8,T8,P0)
            u7   = fan_nozzle.outputs.flow_speed
            rho7 = fan_nozzle.outputs.static_density
            
            
            # Core nozzle flow properties
            
            core_nozzle.compute_static(u6,T6,P0)
            u5   = core_nozzle.outputs.flow_speed
            rho5 = core_nozzle.outputs.static_density       
            
            

            
            #compute offdesign residuals
            
            
            Res = np.zeros([8,M0.shape[1]])
            
            Res[0,:] = (dp.Nf*dp.GF - dp.Nl)
            Res[1,:] = ((1.+f)*dp.mhc*np.sqrt(Tt4_1/Tt2_5)*Pt2_5/Pt4_1 - dp.mhtD)
            Res[2,:] = ((1.+f)*dp.mhc*np.sqrt(Tt4_5/Tt2_5)*Pt2_5/Pt4_5 - dp.mltD)
            Res[3,:] = (dp.mf*np.sqrt(dp.Tref/Tt2)*Pt2/dp.Pref - rho7*u7*dp.A7)
            Res[4,:] = ((1.+f)*dp.mhc*np.sqrt(dp.Tref/Tt2_5)*Pt2_5/dp.Pref - rho5*u5*dp.A5)
            Res[5,:] = (dp.mlc*np.sqrt(dp.Tref/Tt1_9)*Pt1_9/dp.Pref - dp.mhc*np.sqrt(dp.Tref/Tt2_5)*Pt2_5/dp.Pref)           
            Res[6,:] = (dp.Nl - dp.N_spec)
            
            
            # Low pressure turbine off design case
            # A different setup is used for convergence per the TASOPT manual
            
            deltah_lt =  -1./(1.+f)*1./dp.etam_lt*((ht2_5 - ht1_9)+ dp.aalpha*(ht2_1 - ht2))  
            Tt4_9     = Tt4_5 + deltah_lt/Cp
            Pt4_9     = Pt4_5*(Tt4_9/Tt4_5)**(gamma/((gamma-1.)*dp.eta_lt))
            ht4_9     = ht4_5 + deltah_lt                
            
            
            
            Res[7,:] = (dp.Pt5 - Pt4_9*dp.pi_tn)
             
             
            #print f,dp.mhc,Tt4_1,Tt2_5,Pt2_5,Pt4_1,dp.mhtD
             
             
            results.Res = Res
            results.F   = F
            results.mdot = mdot

        
        results.Fsp  = Fsp
        results.Isp  = Isp
        results.sfc  = sfc
        
        
            
            
        return results
    
    
    
    def size(self,mach_number,altitude,delta_isa = 0.):  
        
        #Unpack components
        atmosphere = SUAVE.Analyses.Atmospheric.US_Standard_1976()
        atmo_data = atmosphere.compute_values(altitude,delta_isa)
    
        p   = atmo_data.pressure          
        T   = atmo_data.temperature       
        rho = atmo_data.density          
        a   = atmo_data.speed_of_sound    
        mu  = atmo_data.dynamic_viscosity  
        
        # setup conditions
        conditions = SUAVE.Analyses.Mission.Segments.Conditions.Aerodynamics()            
    
    
    
        # freestream conditions
        
        conditions.freestream.altitude           = np.atleast_1d(altitude)
        conditions.freestream.mach_number        = np.atleast_1d(mach_number)
        
        conditions.freestream.pressure           = np.atleast_1d(p)
        conditions.freestream.temperature        = np.atleast_1d(T)
        conditions.freestream.density            = np.atleast_1d(rho)
        conditions.freestream.dynamic_viscosity  = np.atleast_1d(mu)
        conditions.freestream.gravity            = np.atleast_1d(9.81)
        conditions.freestream.gamma              = np.atleast_1d(1.4)
        conditions.freestream.Cp                 = 1.4*287.87/(1.4-1)
        conditions.freestream.R                  = 287.87
        conditions.freestream.speed_of_sound     = np.atleast_1d(a)
        conditions.freestream.velocity           = conditions.freestream.mach_number * conditions.freestream.speed_of_sound
        
        # propulsion conditions
        conditions.propulsion.throttle           =  np.atleast_1d(1.0)
             
                
        results = self.evaluate(conditions, 0)
        
        self.offdesign_params = deepcopy(self.design_params)
        
        
        
        
        ones_1col = np.ones([1,1])
        altitude      = ones_1col*0.0
        mach_number   = ones_1col*0.0
        throttle      = ones_1col*1.0
        
        #call the atmospheric model to get the conditions at the specified altitude
        atmosphere_sls = SUAVE.Analyses.Atmospheric.US_Standard_1976()
        atmo_data = atmosphere_sls.compute_values(altitude,0.0)
    
        p   = atmo_data.pressure          
        T   = atmo_data.temperature       
        rho = atmo_data.density          
        a   = atmo_data.speed_of_sound    
        mu  = atmo_data.dynamic_viscosity  
    
        # setup conditions
        conditions_sls = SUAVE.Analyses.Mission.Segments.Conditions.Aerodynamics()            
    
    
    
        # freestream conditions
        
        conditions_sls.freestream.altitude           = np.atleast_1d(altitude)
        conditions_sls.freestream.mach_number        = np.atleast_1d(mach_number)
        
        conditions_sls.freestream.pressure           = np.atleast_1d(p)
        conditions_sls.freestream.temperature        = np.atleast_1d(T)
        conditions_sls.freestream.density            = np.atleast_1d(rho)
        conditions_sls.freestream.dynamic_viscosity  = np.atleast_1d(mu)
        conditions_sls.freestream.gravity            = np.atleast_1d(9.81)
        conditions_sls.freestream.gamma              = np.atleast_1d(1.4)
        conditions_sls.freestream.Cp                 = 1.4*287.87/(1.4-1)
        conditions_sls.freestream.R                  = 287.87
        conditions_sls.freestream.speed_of_sound     = np.atleast_1d(a)
        conditions_sls.freestream.velocity           = conditions_sls.freestream.mach_number * conditions_sls.freestream.speed_of_sound
        
        # propulsion conditions
        conditions_sls.propulsion.throttle           =  np.atleast_1d(throttle)
        
        state_sls = Data()
        state_sls.numerics = Data()
        state_sls.conditions = conditions_sls   
        results_sls = self.offdesign(state_sls)
        
        
        
        self.sealevel_static_thrust = results_sls.F
        
        return results






    def evaluate_thrust(self,state):
        
        #imports
        conditions = state.conditions
        numerics   = state.numerics
        throttle = conditions.propulsion.throttle
        
        local_state = copy.deepcopy(state)
        local_throttle = copy.deepcopy(throttle)

        local_throttle[throttle<0.6] = 0.6
        local_throttle[throttle>1.0] = 1.0
        
        local_state.conditions.propulsion.throttle = local_throttle
        
        
        #freestream properties
        T0 = conditions.freestream.temperature
        p0 = conditions.freestream.pressure
        M0 = conditions.freestream.mach_number  
        
        
        F = np.zeros([len(T0),3])
        mdot0 = np.zeros([len(T0),1])
        S  = np.zeros(len(T0))
        F_mdot0 = np.zeros(len(T0))          
        
        results_eval = self.offdesign(local_state)
        
        local_scale = throttle/local_throttle
        
        
        F[:,0] = results_eval.F*local_scale.T
        mdot0[:,0] = results_eval.mdot*local_scale.T
        S = results_eval.TSFC        
        
        #print throttle.T,local_throttle.T,F[:,0],local_scale.T

        
        
        results = Data()
        results.thrust_force_vector = F
        results.vehicle_mass_rate   = mdot0
        results.sfc                 = S    
        
        
        return results




    def offdesign(self,state):
    
    
        dp = deepcopy(self.design_params)
        self.offdesign_params = dp
    
        
    
        conditions = state.conditions
        throttle = conditions.propulsion.throttle
        
        lvals = len(throttle)
        
        self.init_vectors(conditions,dp)
        #print 
        
        #print conditions.freestream.temperature,conditions.freestream.pressure
        
        results = self.evaluate(conditions,1)
        R = results.Res
        bp = self.set_baseline_params(len(throttle))
        #print "Residual : ",R,np.linalg.norm(R)
        #print "Results : ", results.F,results.sfc,self.offdesign_params.Nf,self.offdesign_params.Nl,self.offdesign_params.Nh,self.offdesign_params.mf/self.offdesign_params.mfD,self.offdesign_params.mlc/self.offdesign_params.mlcD,self.offdesign_params.mhc/self.offdesign_params.mhcD
        #print "Updates  : ",bp
        #print 
        
        #print "Results : ", results.Fsp,results.F,results.sfc,self.offdesign_params.Nf,self.offdesign_params.Nl,self.offdesign_params.Nh,self.offdesign_params.mf/self.offdesign_params.mfD,self.offdesign_params.mlc/self.offdesign_params.mlcD,self.offdesign_params.mhc/self.offdesign_params.mhcD
        #print "Res : ",R
        
        
        d_bp = np.zeros([8,lvals])
        
        #print "T",throttle.T,results.F*self.number_of_engines
        
        if(np.linalg.norm(R)>1e-8):
            
            
            
            for iiter in range(0,self.max_iters):
            
                
                J = self.jacobian(conditions,bp,R)
                #print "Jac : ",J
                #print "Res : ",R
                
                #print J.shape,R.shape,d_bp.shape
                #print J[:,:,0].shape,R[:,0].shape,d_bp[:,0].shape
                
                for iarr in range(0,lvals):
                    d_bp[:,iarr] = -np.linalg.solve(J[:,:,iarr], R[:,iarr])
                
                
                
                bp = bp + self.newton_relaxation*d_bp
                self.update_baseline_params(bp)
                results = self.evaluate(conditions,1)
                R = results.Res
                 
                #print R
                
                
                
                #R2 = np.copy(R)
                #R2[4] = 0.0                
                
                #print "Residual : ",R,np.linalg.norm(R),np.linalg.norm(R2),self.offdesign_params.N_spec


                #print "Results : ", R.T , results.Fsp,results.F,results.sfc,self.offdesign_params.Nf,self.offdesign_params.Nl,self.offdesign_params.Nh,self.offdesign_params.mf/self.offdesign_params.mfD,self.offdesign_params.mlc/self.offdesign_params.mlcD,self.offdesign_params.mhc/self.offdesign_params.mhcD
                
                
                
                #print "Updates  : ",bp        
                
                
                
                #print "T",throttle.T,results.F*self.number_of_engines                
                
                
                if(np.linalg.norm(R)<1e-6):
                    break                
                
            
        
                
        
        
                
        results_offdesign = Data()
        results_offdesign.F    = results.F*self.number_of_engines
        results_offdesign.TSFC = results.sfc
        results_offdesign.mdot = results.mdot*self.number_of_engines
        results_offdesign.Tt4  = dp.Tt4_spec
        results_offdesign.Tt3  = dp.Tt3
        results_offdesign.Pt3  = dp.Pt3
        results_offdesign.pi_lc = dp.pi_lc
        results_offdesign.pi_hc = dp.pi_hc
        results_offdesign.pi_f = dp.pi_f
        results_offdesign.flow = dp.mdot_core
        results_offdesign.aalpha = dp.aalpha
        results_offdesign.mdot_fan = dp.aalpha*dp.mdot_core
        results_offdesign.Nl = self.offdesign_params.Nl
        results_offdesign.Nf = self.offdesign_params.Nf
        results_offdesign.Nh = self.offdesign_params.Nh   
        results_offdesign.mlc = self.offdesign_params.mlc
        results_offdesign.mhc = self.offdesign_params.mhc
        results_offdesign.mf = self.offdesign_params.mf           
        
        #print results_offdesign.F,throttle.T,results_offdesign.TSFC
            
        return results_offdesign








    def init_vectors(self,conditions,dp):

        lvals = len(conditions.propulsion.throttle)
        onesv = np.ones([1,lvals])
        
        dp.aalpha  = dp.aalpha*onesv    
        
        dp.pi_d    = dp.pi_d*onesv 
        dp.eta_d   = dp.eta_d*onesv 
        
        dp.pi_f    = dp.pi_f*onesv 
        dp.eta_f   = dp.eta_f*onesv 
        
        dp.pi_fn   = dp.pi_fn*onesv 
        dp.eta_fn  = dp.eta_fn*onesv 
        
        dp.pi_lc   = dp.pi_lc*onesv 
        dp.eta_lc  = dp.eta_lc*onesv 
        
        dp.pi_hc   = dp.pi_hc*onesv 
        dp.eta_hc  = dp.eta_hc*onesv 
        
        dp.Tt4     = dp.Tt4*onesv 
        dp.pi_b    = dp.pi_b*onesv 
        dp.eta_b   = dp.eta_b*onesv 
        
        dp.eta_lt  = dp.eta_lt*onesv 
        dp.etam_lt = dp.etam_lt*onesv 
        
        dp.eta_ht  = dp.eta_ht*onesv 
        dp.etam_ht = dp.etam_ht*onesv 
        
        dp.pi_tn   = dp.pi_tn*onesv 
        dp.eta_tn  = dp.eta_tn*onesv        
        
        dp.mhc = dp.mhc*onesv 
        dp.mlc = dp.mlc*onesv 
        dp.mf  = dp.mf*onesv 
        
        dp.Pt5  = dp.Pt5*onesv 
        dp.Tt4_Tt2 = dp.Tt4_Tt2*onesv        
    




    def set_tem_baseline_params(self,offdesign_params,bp,d_a1,d_bp):
        
        dp = copy.deepcopy(offdesign_params)

        #set the baseline params from the odp array
        dp.pi_f[0,:]  = bp[0,:] + d_a1*d_bp[0,:]
        dp.pi_lc[0,:] = bp[1,:] + d_a1*d_bp[1,:]
        dp.pi_hc[0,:] = bp[2,:] + d_a1*d_bp[2,:]
        dp.mf[0,:]    = bp[3,:] + d_a1*d_bp[3,:]
        dp.mlc[0,:]   = bp[4,:] + d_a1*d_bp[4,:]
        dp.mhc[0,:]   = bp[5,:] + d_a1*d_bp[5,:]
        dp.Tt4[0,:]   = bp[6,:] + d_a1*d_bp[6,:]
        dp.Pt5[0,:]   = bp[7,:] + d_a1*d_bp[7,:]
        
        return dp




    def set_baseline_params(self,lvals):
        
        dp = self.offdesign_params
        bp = np.zeros([8,lvals])
        #set the baseline params from the odp array
        bp[0,:] = dp.pi_f[0,:]
        bp[1,:] = dp.pi_lc[0,:]
        bp[2,:] = dp.pi_hc[0,:]
        bp[3,:] = dp.mf[0,:]
        bp[4,:] = dp.mlc[0,:]
        bp[5,:] = dp.mhc[0,:]
        bp[6,:] = dp.Tt4[0,:]
        bp[7,:] = dp.Pt5[0,:]
        
        return bp
    
    
    
    
    
    def update_baseline_params(self,bp):
    
        dp = self.offdesign_params
        #set the baseline params from the odp array
        dp.pi_f[0,:]  = bp[0,:]
        dp.pi_lc[0,:] = bp[1,:]
        dp.pi_hc[0,:] = bp[2,:]
        dp.mf[0,:]    = bp[3,:]
        dp.mlc[0,:]   = bp[4,:]
        dp.mhc[0,:]   = bp[5,:]
        dp.Tt4[0,:]   = bp[6,:]
        dp.Pt5[0,:]   = bp[7,:]       
    
 
        return
    
    

    
    def jacobian(self,conditions,bp,R):
        
        dd = 1e-8
        dp_temp = deepcopy(self.offdesign_params) 
        lvals = len(conditions.propulsion.throttle)
        jacobian = np.zeros([8,8,lvals])
        
        network_params = [dp_temp.pi_f,dp_temp.pi_lc,dp_temp.pi_hc,dp_temp.mf,dp_temp.mlc,dp_temp.mhc,dp_temp.Tt4,dp_temp.Pt5]
        
        design_run = False
        
        for i, network_param in enumerate(network_params):
                network_param[0,:] = bp[i,:]*(1.+dd)
                results            = self.evaluate(conditions, 1., dp_temp)
                network_param[0,:] = bp[i,:]
                jacobian[i,:,:]    = (results.Res - R)/(bp[i,:]*dd) 
        
        jacobian = np.swapaxes(jacobian, 0, 1)


        return jacobian
        
        
        
        
        
        
        
           
        
        
        
        


    def engine_out(self,state):
        
        
        temp_throttle = np.zeros(len(state.conditions.propulsion.throttle))
        
        for i in range(0,len(state.conditions.propulsion.throttle)):
            temp_throttle[i] = state.conditions.propulsion.throttle[i]
            state.conditions.propulsion.throttle[i] = 1.0
        
        
        
        results = self.evaluate_thrust(state)
        
        for i in range(0,len(state.conditions.propulsion.throttle)):
            state.conditions.propulsion.throttle[i] = temp_throttle[i]
        
        
        
        results.thrust_force_vector = results.thrust_force_vector/self.number_of_engines*(self.number_of_engines-1)
        results.vehicle_mass_rate   = results.vehicle_mass_rate/self.number_of_engines*(self.number_of_engines-1)
        
        
        
        return results
        
        #return    



    __call__ = evaluate_thrust
