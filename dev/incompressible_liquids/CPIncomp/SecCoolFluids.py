from __future__ import division, absolute_import, print_function
import numpy as np
from CPIncomp.CoefficientObjects import CoefficientData
from CPIncomp.BaseObjects import IncompressibleData
from CPIncomp.DataObjects import DigitalData
import os, CPIncomp



class SecCoolSolutionData(DigitalData):
    """ 
    A base class that can be fed with a fluid ID from SecCool
    to read data files sitting in data/SecCool/xMass and 
    data/SecCool/xVolume. 
    """ 
    def __init__(self,sFile=None,sFolder=None,name=None,desc=None,ref='SecCool software'):
        DigitalData.__init__(self)
        self.allowNegativeData = False
        
        if sFile   == None: raise ValueError("File name cannot be empty.")
        if sFolder == None: raise ValueError("Folder name cannot be empty.")
        if name    == None: raise ValueError("Fluid name cannot be empty.")
        if desc    == None: raise ValueError("Description cannot be empty.")
        
        self.sFile   = sFile
        self.sFolder = sFolder
        
        self.name = name
        self.description = desc
        self.reference = ref
                
        self.density.data       = self.getArray(data='Rho')
                
        self.Tmax = np.max(self.temperature.data)
        self.Tmin = np.min(self.temperature.data)
        self.xmax = np.max(self.concentration.data)
        self.xmin = np.min(self.concentration.data)
        if self.sFolder=='xVolume':
            self.xid  = self.ifrac_volume
        elif self.sFolder=='xMass':
            self.xid  = self.ifrac_mass
        elif self.sFolder=='xPure':
            self.xid  = self.ifrac_pure
        else:
            raise ValueError("Unknown folder type specified.")        
        self.TminPsat = self.Tmax
        
        self.Tbase = (self.Tmin + self.Tmax) / 2.0
        self.xbase = (self.xmin + self.xmax) / 2.0
        
        
    def fitFluid(self):
        std_coeffs = np.zeros((4,6))
        errList    = (ValueError, AttributeError, TypeError, RuntimeError)
        
        tempData = np.copy(self.temperature.data)
        concData = np.copy(self.concentration.data)
        
        
        try:
            self.temperature.data = None
            self.concentration.data = None
            self.density.data   = self.getArray(data='Rho')
            self.density.coeffs = np.copy(std_coeffs)
            self.density.type   = self.density.INCOMPRESSIBLE_POLYNOMIAL
            self.density.fitCoeffs(tempData,concData,self.Tbase,self.xbase)
        except errList as ve:
            if self.density.DEBUG: print("{0}: Could not fit polynomial {1} coefficients: {2}".format(self.name,'density',ve))
            pass
        
        try:
            self.temperature.data = None
            self.concentration.data = None
            self.specific_heat.data   = self.getArray(data='Cp')
            while np.max(self.specific_heat.data)<100: # Expect values around 1e3
                self.specific_heat.data *= 1e3 
            self.specific_heat.coeffs = np.copy(std_coeffs)
            self.specific_heat.type   = self.specific_heat.INCOMPRESSIBLE_POLYNOMIAL
            self.specific_heat.fitCoeffs(tempData,concData,self.Tbase,self.xbase)
        except errList as ve:
            if self.specific_heat.DEBUG: print("{0}: Could not fit polynomial {1} coefficients: {2}".format(self.name,'specific heat',ve))
            pass 
        
        try:
            self.temperature.data = None
            self.concentration.data = None
            self.conductivity.data   = self.getArray(data='Cond')
            while np.max(self.conductivity.data)>10: # Expect value below 1
                self.conductivity.data *= 1e-3 
            self.conductivity.coeffs = np.copy(std_coeffs)
            self.conductivity.type   = self.conductivity.INCOMPRESSIBLE_POLYNOMIAL
            self.conductivity.fitCoeffs(tempData,concData,self.Tbase,self.xbase)
        except errList as ve:
            if self.conductivity.DEBUG: print("{0}: Could not fit polynomial {1} coefficients: {2}".format(self.name,'conductivity',ve))
            pass
        
        try:
            self.temperature.data = None
            self.concentration.data = None
            self.viscosity.data   = self.getArray(data='Mu')
            while np.max(self.viscosity.data)>100: # Expect value below 10
                self.viscosity.data *= 1e-3 
            self.viscosity.coeffs = np.copy(std_coeffs)
            self.viscosity.type   = self.viscosity.INCOMPRESSIBLE_EXPPOLYNOMIAL
            self.viscosity.fitCoeffs(tempData,concData,self.Tbase,self.xbase)
        except errList as ve:
            if self.viscosity.DEBUG: print("{0}: Could not fit polynomial {1} coefficients: {2}".format(self.name,'viscosity',ve))
            pass
        
        # reset data for getArray and read special files
        if self.xid!=self.ifrac_pure and self.xid!=self.ifrac_undefined:
            self.temperature.data = None
            self.concentration.data = None
            allowNegativeData_org = self.allowNegativeData
            self.allowNegativeData = True
            Tfreeze_T = self.getArray(data='TFreeze')
            if np.min(Tfreeze_T)<150: Tfreeze_T += 273.15 
            Tfreeze_x = (self.temperature.data - 273.15) / 100.0
            self.T_freeze.data = Tfreeze_T
            try:        
                self.T_freeze.coeffs = np.copy(std_coeffs)
                self.T_freeze.type   = self.T_freeze.INCOMPRESSIBLE_POLYNOMIAL
                self.T_freeze.fitCoeffs(Tfreeze_x,0.0,self.xbase,0.0)
            except errList as ve:
                if self.T_freeze.DEBUG: print("{0}: Could not fit {1} coefficients: {2}".format(self.name,"T_freeze",ve))
                pass

            # reset data for getArray again
            self.temperature.data = None
            self.concentration.data = None
            self.allowNegativeData = allowNegativeData_org
            massData =  self.getArray(data='Vol2Mass')[:,0]/100.0
            volData  = (self.temperature.data - 273.15)    /100.0
            if self.xid==self.ifrac_volume:
                _,_,self.mass2input.data = IncompressibleData.shapeArray(volData,axs=1)
                #_,_,massData = IncompressibleData.shapeArray(massData,axs=1)
                try:
                    self.mass2input.coeffs = np.copy(std_coeffs)
                    self.mass2input.type   = self.mass2input.INCOMPRESSIBLE_POLYNOMIAL
                    self.mass2input.fitCoeffs([self.Tbase],massData,self.Tbase,self.xbase)
                except errList as ve:
                    if self.mass2input.DEBUG: print("{0}: Could not fit {1} coefficients: {2}".format(self.name,"mass2input",ve))
                    pass
            elif self.xid==self.ifrac_mass:
                _,_,self.volume2input.data = IncompressibleData.shapeArray(massData,axs=1)
                #_,_,volData = IncompressibleData.shapeArray(volData,axs=1)
                try:
                    self.volume2input.coeffs = np.copy(std_coeffs)
                    self.volume2input.type   = self.volume2input.INCOMPRESSIBLE_POLYNOMIAL
                    self.volume2input.fitCoeffs([self.Tbase],volData,self.Tbase,self.xbase)
                except errList as ve:
                    if self.volume2input.DEBUG: print("{0}: Could not fit {1} coefficients: {2}".format(self.name,"volume2input",ve))
                    pass
            else:
                raise ValueError("Unknown xid specified.")
        
        # reset temperature and concentration to real values     
        self.temperature.data = tempData
        self.concentration.data = concData
        #self.Tbase =  -4.48 + 273.15
        #self.xbase =  31.57 / 100.0
        
    # Redefine some functions to avoid data loss
    def getFile(self, data):
        return os.path.join(CPIncomp.__path__[0], 'data','SecCool', self.sFolder, self.sFile+"_"+data+".txt")
    
    def getFromFile(self, data):
        fullPath = self.getFile(data)
        r,c,res = IncompressibleData.shapeArray(np.loadtxt(fullPath,dtype=type('string')))
#        numbers = res.astype(np.float)
        numbers = np.zeros((r,c))
        for i in range(r):
            for j in range(c):
                nu = np.NAN
                try:
                    nu = np.float(res[i,j])
                    if i==0: nu *= 1e-2 # Percent to fraction
                    if j==0: nu += 273.15 # Celsius to Kelvin
                    if not self.allowNegativeData and nu<0:
                        nu = np.NAN # invalid entries
                except (ValueError, TypeError) as ve:
                    #print "Could not convert entry: {0}".format(ve)
                    if i==0: nu = 0.0 # Dummy for tables without concentration (TFreeze and Vol2Mass)
                    pass
                numbers[i,j] = nu
        if numbers[1,0]>numbers[-1,0]: 
            numbers[1:,:] = numbers[1:,:][::-1,:]
        if numbers[0,1]>numbers[0,-1]: 
            numbers[:,1:] = numbers[:,1:][:,::-1]
        return numbers 
    
    def writeToFile(self, data, array):
        raise ValueError("You should not overwrite the SecCool data.")
        
    @staticmethod
    def factory():
        """
        A static method that returns a list of SecCool
        solutions. Coefficients are fitted by calling
        fitFluid and then the objects should be ready 
        to be written to JSON.
        """
        print("Loading SecCool fluids: ", end="")        
        sec = []
        sec += [SecCoolSolutionData(sFile='Antifrogen KF'           ,sFolder='xVolume',name='AKF',desc='Antifrogen KF, Potassium Formate'       ,ref='Clariant GmbH Jan. 2000, SecCool software')]
        print("{0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Antifrogen L'            ,sFolder='xVolume',name='AL' ,desc='Antifrogen L, Propylene Glycol'         ,ref='Clariant GmbH Jan. 2000, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Antifrogen N'            ,sFolder='xVolume',name='AN' ,desc='Antifrogen N, Ethylene Glycol'          ,ref='Clariant GmbH Jan. 2000, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='ASHRAE, Ethylene Glycol' ,sFolder='xVolume',name='AEG',desc='ASHRAE, Ethylene Glycol'                ,ref='ASHRAE Fundamentals Handbook 2001, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='ASHRAE, Propylene Glycol',sFolder='xVolume',name='APG',desc='ASHRAE, Propylene Glycol'               ,ref='ASHRAE Fundamentals Handbook 2001, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Glykosol N'              ,sFolder='xVolume',name='GKN',desc='Glykosol N, Ethylene Glycol'            ,ref='pro KUEHLSOLE GmbH, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Pekasol 2000'            ,sFolder='xVolume',name='PK2',desc='Pekasol 2000, Potassium acetate/formate',ref='pro KUEHLSOLE GmbH, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Pekasol L'               ,sFolder='xVolume',name='PKL',desc='Pekasol L, Propylene Glycol'            ,ref='pro KUEHLSOLE GmbH, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Zitrec AC'               ,sFolder='xVolume',name='ZAC',desc='Zitrec AC, Corrosion Inhibitor'         ,ref='Arteco, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Zitrec FC'               ,sFolder='xVolume',name='ZFC',desc='Zitrec FC, Propylene Glycol'            ,ref='Arteco, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Zitrec LC'               ,sFolder='xVolume',name='ZLC',desc='Zitrec LC, Propylene Glycol'            ,ref='Arteco, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Zitrec MC'               ,sFolder='xVolume',name='ZMC',desc='Zitrec MC, Ethylene Glycol'             ,ref='Arteco, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Zitrec M'                ,sFolder='xVolume',name='ZM' ,desc='Zitrec M, Ethylene Glycol'              ,ref='Arteco, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        
        sec += [SecCoolSolutionData(sFile='Melinder, Ammonia'            ,sFolder='xMass',name='MAM2',desc='Melinder, Ammonia'            ,ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Melinder, Calcium Cloride'    ,sFolder='xMass',name='MCA2',desc='Melinder, Calcium Chloride'   ,ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Melinder, Ethanol'            ,sFolder='xMass',name='MEA2',desc='Melinder, Ethanol'            ,ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Melinder, Ethylene glycol'    ,sFolder='xMass',name='MEG2',desc='Melinder, Ethylene Glycol'    ,ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Melinder, Glycerol'           ,sFolder='xMass',name='MGL2',desc='Melinder, Glycerol'           ,ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Melinder, Magnesium Chloride' ,sFolder='xMass',name='MMG2',desc='Melinder, Magnesium Chloride' ,ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Melinder, Methanol'           ,sFolder='xMass',name='MMA2',desc='Melinder, Methanol'           ,ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Melinder, Potassium Acetate'  ,sFolder='xMass',name='MKA2',desc='Melinder, Potassium Acetate'  ,ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Melinder, Potassium Carbonate',sFolder='xMass',name='MKC2',desc='Melinder, Potassium Carbonate',ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Melinder, Propylene Glycol'   ,sFolder='xMass',name='MPG2',desc='Melinder, Propylene Glycol'   ,ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Melinder, Sodium Chloride'    ,sFolder='xMass',name='MNA2',desc='Melinder, Sodium Chloride'    ,ref='Melinder-BOOK-2010, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='VDI, Calcium Cloride'         ,sFolder='xMass',name='VCA' ,desc='VDI, Calcium Cloride'         ,ref='VDI Waermeatlas 9th Edition 2002, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='VDI, Magnesium Chloride'      ,sFolder='xMass',name='VMG' ,desc='VDI, Magnesium Chloride'      ,ref='VDI Waermeatlas 9th Edition 2002, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='VDI, Methanol'                ,sFolder='xMass',name='VMA' ,desc='VDI, Methanol'                ,ref='VDI Waermeatlas 9th Edition 2002, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='VDI, Potassium Carbonate'     ,sFolder='xMass',name='VKC' ,desc='VDI, Potassium Carbonate'     ,ref='VDI Waermeatlas 9th Edition 2002, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='VDI, Sodium Chloride'         ,sFolder='xMass',name='VNA' ,desc='VDI, Sodium Chloride'         ,ref='VDI Waermeatlas 9th Edition 2002, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")

        sec += [SecCoolSolutionData(sFile='HFE-7100'     ,sFolder='xPure',name='HFE' ,desc='HFE-7100, Hydrofluoroether'                      ,ref='3M Novec, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='NBS, Water'   ,sFolder='xPure',name='NBS' ,desc='NBS, Water'                                      ,ref='Properties of Water and Steam in SI-Units, 2nd Revised and Updated Printing, Springer 1979, pp. 175 ff., SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Paracryol'    ,sFolder='xPure',name='PCL' ,desc='Paracryol, Aliphatic Hydrocarbon'                ,ref='Sulzer Chemtech AG, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Paratherm NF' ,sFolder='xPure',name='PNF' ,desc='Paratherm NF, Hydrotreated mineral oil'          ,ref='Paratherm Ltd, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Tyfoxit 1.10' ,sFolder='xPure',name='TY10',desc='Tyfoxit 1.10, Potassium Acetate'                 ,ref='Tyforop Chemie Gmbh - Technical information 09/99, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Tyfoxit 1.15' ,sFolder='xPure',name='TY15',desc='Tyfoxit 1.15, Potassium Acetate'                 ,ref='Tyforop Chemie Gmbh - Technical information 09/99, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Tyfoxit 1.20' ,sFolder='xPure',name='TY20',desc='Tyfoxit 1.20, Potassium Acetate'                 ,ref='Tyforop Chemie Gmbh - Technical information 09/99, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Tyfoxit 1.24' ,sFolder='xPure',name='TY24',desc='Tyfoxit 1.24, Potassium Acetate'                 ,ref='Tyforop Chemie Gmbh - Technical information 09/99, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Zitrec S10'   ,sFolder='xPure',name='ZS10',desc='Zitrec S10, Potassium formate/Sodium propionate' ,ref='Arteco, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Zitrec S25'   ,sFolder='xPure',name='ZS25',desc='Zitrec S25, Potassium formate/Sodium propionate' ,ref='Arteco, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Zitrec S40'   ,sFolder='xPure',name='ZS40',desc='Zitrec S40, Potassium formate/Sodium propionate' ,ref='Arteco, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Zitrec S45'   ,sFolder='xPure',name='ZS45',desc='Zitrec S45, Potassium formate/Sodium propionate' ,ref='Arteco, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        sec += [SecCoolSolutionData(sFile='Zitrec S55'   ,sFolder='xPure',name='ZS55',desc='Zitrec S55, Potassium formate/Sodium propionate' ,ref='Arteco, SecCool software')]
        print(", {0}".format(sec[-1].name), end="")
        
        print(" ... done")
        
        return sec





