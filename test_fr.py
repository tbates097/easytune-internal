# -*- coding: utf-8 -*-
"""
Created on Fri May 30 11:36:44 2025

@author: MECHASSY
"""

import automation1 as a1

controller = a1.Controller.connect()
name = controller.name
print(f"Controller: {name}")
axis = 'X'
params = controller.configuration.parameters.get_configuration()
motor_pole_pitch = params.axes[axis].motor.motorpolepitch.value
distance = motor_pole_pitch / 2
speed = distance * 0.1
# Generate the FR file
fr_filename = 'test.fr'
axis = axis


fr_string = fr'AppFrequencyResponseTriggerMultisinePlus({axis}, "{fr_filename}", 10, 2500, 280, 5, TuningMeasurementType.ServoOpenLoop, {distance}, {speed})'
controller.runtime.commands.execute(fr_string)
#controller.runtime.commands.execute(fr'AppFrequencyResponseTriggerMultisinePlus({axis}, "{fr_filename}", 10, 2500, 280, 10, TuningMeasurementType.ServoOpenLoop, 15, 1.5)', 1)
print("Finished")