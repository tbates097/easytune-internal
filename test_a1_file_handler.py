import sys
import os

sys.path.append(r"K:\10. Released Software\Shared Python Programs\production-2.1")
from a1_file_handler import DatFile 
from a1_file_handler import PlotFile

def dat_to_plt():
    test_dir = r'C:\Users\tbates\Documents\Automation1\TestDatFiles'
    convert_to_plt = DatFile()

    PLOT = convert_to_plt.create_from_file(os.path.join(test_dir, 'stage_performance_multi_NE_SW_20250724_100740.dat'))

    print(PLOT.data_structure_list)
    print(PLOT.data_structure_list[0])  # or any index
    print(PLOT.all_data.keys())         # to see the available signal names

def plt_to_dat():
    test_dir = r'C:\Users\tbates\Documents\Automation1\TestPltFiles'
    convert_to_dat = PlotFile()

    DAT = convert_to_dat.create_from_file(os.path.join(test_dir, 'NE-SW.plt'))

    print(DAT.all_data.keys())

def main(convert_to):
    if convert_to == 'dat_to_plt':
        dat_to_plt()
    elif convert_to == 'plt_to_dat':
        plt_to_dat()
    else:
        print('Invalid conversion type')

if __name__ == '__main__':
    main('plt_to_dat')