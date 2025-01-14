"""This module is used to convert the data file to the raw data file for upload to the database."""
import csv
import re
import math
import os
import itkdb
import numpy as np
import module_metrology as mm
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog
from tkinter import scrolledtext
from tkinter.constants import DISABLED, NORMAL
from tkinter import END

# Institute Specific Constants - MODIFY THESE!
INSTITUTE = 'TRIUMF'
INSTRUMENT = "Mitutoyo CMM"
SITE_TYPE = 'EC'
HYBRID_FLEX_THICKNESS = 250 #um (Endcap)
PB_FLEX_THICKNESS = 270 #um (Endcap)
MAX_SHIELD_HEIGHT = 5710 #um (Endcap)

# Do not modify.
X_LIMIT = 100 #um
Y_LIMIT = 300 #um
PATH_TO_DATA = 'module_metrology_data/metrology_data/'
PATH_TO_POSITION_FILES = 'metrology_position_files/'
PROGRAM_VERSION = 'v1'
GLUE_RANGE = (80, 160) #um
X = 0
Y = 1
Z = 2
ENTRY_X = 100
ENTRY_Y = 20
DATA_DICT = dict()
HYBRID_GT_REGEX = '_R[0-5]H[0-1]_[0-9]+'
PB_GT_REGEX = 'PB_[0-5]'
SHIELD_REGEX = 'Shield'
CAP_REGEX = 'C[1-8]'

def get_comp_dict(module_type):
    """Gets the postision dictionary to determine flex offsets."""
    file_name = PATH_TO_POSITION_FILES + module_type + "_positions.csv"
    with open(file_name) as csv_file :
        reader = csv.reader(csv_file, delimiter = ',')
        positions = list(reader)
    comparison_dict = dict()
    for row in positions[1:]:
        comparison_dict[row[0]] = [float(row[1]), float(row[2])]
    return comparison_dict

def round(number, decimal=2):
    """Truncates a float to a value given by decimal. Default is 2 decimal places."""
    factor = 10.0 ** decimal
    return math.trunc(number * factor)/ factor

def print_format(data):
    """Formats for printing"""
    output = ""
    if type(data) == dict:
        for key, values in data.items():
            output += str(key) + ": " + str(values) + "\n"
    else:
        output = str(data)
    return output


def get_metrology_results(lines):
    """Creates the results dictionary for upload to the database."""
    results = dict()
    index = 12 # Skip the header

    # Hybrid and Powerboard positions
    hybrid_dict = dict()
    pb_dict = dict()
    comparison_dict = get_comp_dict(lines[2].split()[2])
    line_data = lines[index]
    while '#' not in line_data :
        name, x, y = line_data.split()
        x_expected, y_expected = comparison_dict[name]
        if "H" in name : #Hybrid point
            hybrid_dict[name] = [round((float(x) - x_expected)*1000), round((float(y) - y_expected)*1000)]
        else :
            pb_dict[name] = [round((float(x) - x_expected)*1000), round((float(y) - y_expected)*1000)]
        index += 1
        line_data = lines[index]

    # Get rest of data and correct tilt
    raw_data_dict = dict()
    for line in lines[index:] :
        if '#' not in line :
            name, measure_type, x, y ,z = line.split()
            temp_list = raw_data_dict.get(name, [])
            temp_list.append([float(x),float(y),float(z)])
            raw_data_dict[name] = temp_list
    data_dict = mm.tilt_correction(raw_data_dict)
    # print(data_dict)
    #Get rest of results
    cap_dict = dict()
    hybrid_gt_dict = dict()
    pb_gt_dict = dict()
    shield_height = None
    for key, values in data_dict.items() :
        z_values = [round(row[Z], 4) for row in values]
        if re.search(CAP_REGEX, key) :
            cap_dict[key] = round(sum(z_values)/len(z_values)*1000)
        elif re.search(HYBRID_GT_REGEX, key) :
            hybrid_gt_dict[key] = round(sum(np.array(z_values)*1000 - HYBRID_FLEX_THICKNESS)/len(z_values))
        elif re.search(PB_GT_REGEX, key) :
            pb_gt_dict[key] = round(sum(np.array(z_values)*1000 - PB_FLEX_THICKNESS)/len(z_values))
        elif re.search(SHIELD_REGEX, key) :
            shield_height = round(max(z_values)*1000)

    if not cap_dict :
        results["CAP_HEIGHT"] = None
    else :
        results["CAP_HEIGHT"] = cap_dict
    if not pb_dict :
        results["PB_POSITION"] = None
    else :
        results["PB_POSITION"] = pb_dict
    if not pb_gt_dict :
        results["PB_GLUE_THICKNESS"] = None
    else :
        results["PB_GLUE_THICKNESS"] = pb_gt_dict
    results["HYBRID_POSITION"] = hybrid_dict
    results["HYBRID_GLUE_THICKNESS"] = hybrid_gt_dict
    results["SHIELDBOX_HEIGHT"] = shield_height
    results["FILE"] = ""
    print(results)

    plt.figure(1)
    fig, ax = plt.subplots()
    ax.plot(cap_dict.keys(), cap_dict.values(), 'k-', label = "glue height")
    ax.plot(cap_dict.keys(), np.full((len(cap_dict), 1), GLUE_RANGE[0]), 'r--', label = "min")
    ax.plot(cap_dict.keys(), np.full((len(cap_dict), 1), GLUE_RANGE[1]), 'r--', label = "max")
    # plt.plot([1, 2, 3, 4])
    plt.title("Capacitor Package Heights")
    plt.ylabel("Glue Thickness [um]")

    plt.figure(2)
    fig1, ax = plt.subplots()
    ax.plot(hybrid_gt_dict.keys(), hybrid_gt_dict.values(), 'k-', label="glue height")
    ax.plot(hybrid_gt_dict.keys(), np.full((len(hybrid_gt_dict), 1), GLUE_RANGE[0]), 'r--', label="min")
    ax.plot(hybrid_gt_dict.keys(), np.full((len(hybrid_gt_dict), 1), GLUE_RANGE[1]), 'r--', label="max")
    # plt.plot([1, 2, 3, 4])
    plt.title("Hybrid Glue Heights")
    plt.ylabel("Glue Thickness [um]")

    plt.figure(3)
    fig2, ax = plt.subplots()
    ax.plot(pb_gt_dict.keys(), pb_gt_dict.values(), 'k-', label="glue height")
    ax.plot(pb_gt_dict.keys(), np.full((len(pb_gt_dict), 1), GLUE_RANGE[0]), 'r--', label="min")
    ax.plot(pb_gt_dict.keys(), np.full((len(pb_gt_dict), 1), GLUE_RANGE[1]), 'r--', label="max")
    # plt.plot([1, 2, 3, 4])
    plt.title("Powerboard Glue Heights")
    plt.ylabel("Glue Thickness [um]")
    plt.show()
    return results

def test_passed():
    """returns true or false for wheather the test passed"""
    output = "File processed.\n"

    # Check glue thickness
    x_positions = []
    y_positions = []
    for point in DATA_DICT['results']['HYBRID_POSITION'].values():
        x_positions.append(point[X])
        y_positions.append(point[Y])
    if DATA_DICT['results']['PB_POSITION'] is not None :
        for point in DATA_DICT['results']['PB_POSITION'].values():
            x_positions.append(point[X])
            y_positions.append(point[Y])

    position_x_check =  -X_LIMIT < np.abs(np.array(x_positions)).all() < X_LIMIT
    position_y_check =  -Y_LIMIT < np.abs(np.array(y_positions)).all() < Y_LIMIT
    if not position_x_check or not position_y_check:
        output += "Failure - Position exceeds tolerance in one or more dimensions.\n"


    # Check the hybrid glue thickness
    hybrid_gts = []
    for height in DATA_DICT['results']['HYBRID_GLUE_THICKNESS'].values():
        hybrid_gts.append(height)
    # hybrid_gt_check = GLUE_RANGE[0] < np.array(hybrid_gts).all() < GLUE_RANGE[1]
    hybrid_gt_check = all(GLUE_RANGE[0] < gt < GLUE_RANGE[1] for gt in np.array(hybrid_gts))
    if not hybrid_gt_check:
        output += "Failure - Hybrid glue thickness exceeds tolerance.\n"

    # Then the powerboard
    if DATA_DICT['results']['PB_GLUE_THICKNESS'] is not None :
        pb_gts = []
        for height in DATA_DICT['results']['PB_GLUE_THICKNESS'].values():
            pb_gts.append(height)
        pb_gt_check = all(GLUE_RANGE[0] < gt < GLUE_RANGE[1] for gt in np.array(pb_gts))
        if not pb_gt_check:
            output += "Failure - PB glue thickness exceeds tolerance.\n"
    else:
        pb_gt_check = True

    # Check the shieldbox height
    if DATA_DICT['results']['SHIELDBOX_HEIGHT'] is not None:
        shield_check = DATA_DICT['results']['SHIELDBOX_HEIGHT'] < MAX_SHIELD_HEIGHT
        if not shield_check:
            output += "Failure - Sheild is too high.\n"
    else:
         shield_check = True
    
    if all([position_x_check, position_y_check, hybrid_gt_check, pb_gt_check, shield_check]):
        output += 'All tests passed! Proceed to upload.'
    else:
        output += 'One or more failures. Upload if you wish.'

    output_text.set(output)
    return all([position_x_check, position_y_check, hybrid_gt_check, pb_gt_check, shield_check])
        

def get_file_data():
    """Get the data from a file using the search function and format it into the standard JSON dictionary."""
    # Clear previous results to allow for multiple uploads.
    DATA_DICT.clear()
    id_box.configure(state=NORMAL)
    run_num_box.configure(state=NORMAL)
    operator_box.configure(state=NORMAL)
    hybrid_deviations_box.configure(state=NORMAL)
    pb_deviations_box.configure(state=NORMAL)
    hybrid_gt_box.configure(state=NORMAL)
    pb_gt_box.configure(state=NORMAL)
    cap_height_box.configure(state=NORMAL)
    shield_height_box.configure(state=NORMAL)

    id_box.delete('1.0', END)
    run_num_box.delete('1.0', END)
    operator_box.delete('1.0', END)
    hybrid_deviations_box.delete('1.0', END)
    pb_deviations_box.delete('1.0', END)
    hybrid_gt_box.delete('1.0', END)
    pb_gt_box.delete('1.0', END)
    cap_height_box.delete('1.0', END)
    shield_height_box.delete('1.0', END)

    id_box.configure(state=DISABLED)
    run_num_box.configure(state=DISABLED)
    operator_box.configure(state=DISABLED)
    hybrid_deviations_box.configure(state=DISABLED)
    pb_deviations_box.configure(state=DISABLED)
    hybrid_gt_box.configure(state=DISABLED)
    pb_gt_box.configure(state=DISABLED)
    cap_height_box.configure(state=DISABLED)
    shield_height_box.configure(state=DISABLED)

    file = filedialog.askopenfilename(initialdir = PATH_TO_DATA, title = 'Select Data File')
    
    # Get the data from the file
    with open(file) as data_file:
        lines = data_file.readlines()
    DATA_DICT["component"] = lines[3].split()[3]
    DATA_DICT["testType"] = "MODULE_METROLOGY"
    DATA_DICT["institution"] = lines[5].split()[1]
    DATA_DICT["runNumber"] = str(lines[8].split()[2])
    DATA_DICT["date"] = lines[4].split()[1]
    DATA_DICT["passed"] = ""
    DATA_DICT["problems"] = ""
    properties = dict()
    machine = lines[7].split()
    operator = lines[6].split()
    properties["MACHINE"] = " ".join(machine[2:])
    properties["OPERATOR"] = " ".join(operator[1:])
    properties["SCRIPT_VERSION"] = lines[9].split()[3] 
    DATA_DICT["properties"] = properties 
    DATA_DICT["results"] = get_metrology_results(lines)
    DATA_DICT["results"]["FILE"] = file
    DATA_DICT['passed'] = test_passed()
    
    # Update the output for the user.
    id_box.configure(state=NORMAL)
    run_num_box.configure(state=NORMAL)
    operator_box.configure(state=NORMAL)
    hybrid_deviations_box.configure(state=NORMAL)
    pb_deviations_box.configure(state=NORMAL)
    hybrid_gt_box.configure(state=NORMAL)
    pb_gt_box.configure(state=NORMAL)
    cap_height_box.configure(state=NORMAL)
    shield_height_box.configure(state=NORMAL)

    id_box.insert('1.0', DATA_DICT["component"])
    run_num_box.insert('1.0', DATA_DICT["runNumber"])
    operator_box.insert('1.0', DATA_DICT["properties"]["OPERATOR"])
    hybrid_deviations_box.insert('1.0', print_format(DATA_DICT["results"]["HYBRID_POSITION"]))
    pb_deviations_box.insert('1.0', print_format(DATA_DICT["results"]["PB_POSITION"]))
    hybrid_gt_box.insert('1.0', print_format(DATA_DICT["results"]["HYBRID_GLUE_THICKNESS"]))
    pb_gt_box.insert('1.0', print_format(DATA_DICT["results"]["PB_GLUE_THICKNESS"]))
    cap_height_box.insert('1.0', print_format(DATA_DICT["results"]["CAP_HEIGHT"]))
    if DATA_DICT["results"]["SHIELDBOX_HEIGHT"] is not None :
        shield_height_box.insert('1.0', DATA_DICT["results"]["SHIELDBOX_HEIGHT"])
    else : 
        shield_height_box.insert('1.0', 'None')

    id_box.configure(state=DISABLED)
    run_num_box.configure(state=DISABLED)
    operator_box.configure(state=DISABLED)
    hybrid_deviations_box.configure(state=DISABLED)
    pb_deviations_box.configure(state=DISABLED)
    hybrid_gt_box.configure(state=DISABLED)
    pb_gt_box.configure(state=DISABLED)
    cap_height_box.configure(state=DISABLED)
    shield_height_box.configure(state=DISABLED)


def save_data():
    """Saves a metrology data file in the standard file format"""
    if problems_box.curselection() == () or DATA_DICT == {}:
        output_text.set('Please ensure all mandatory values have been entered and a data file has been choosen. Then try again.')
        return 
    else:
        if problems_box.get(problems_box.curselection()[0]) == "Yes":
             DATA_DICT["problems"]  = True
        else: 
            DATA_DICT["problems"] = False

    db_passcode_1 =  db_pass_1.get()
    db_passcode_2 =  db_pass_2.get()

    try :
        user = itkdb.core.User(accessCode1 = db_passcode_1, accessCode2 = db_passcode_2)
        client = itkdb.Client(user=user)
    except:
        output_text.set("Set passcodes are incorrect. Try again")
        return
    
    result= client.post("uploadTestRunResults", json = DATA_DICT)

    if (('uuAppErrorMap')=={}):
        output_text.set('Upload of Test and File Succesful!')
    elif (('uuAppErrorMap'))[0]=='cern-itkpd-main/uploadTestRunResults/':
        output_text.set("Error in Test Upload.")
    elif list(('uuAppErrorMap'))[0]=='cern-itkpd-main/uploadTestRunResults/componentAtDifferentLocation':
        output_text.set('Component cannot be uploaded as is not currently at the given location')
    elif (('uuAppErrorMap'))[0]=='cern-itkpd-main/uploadTestRunResults/unassociatedStageWithTestType':
        output_text.set('Component cannot be uploaded as the current stage does not have this test type. You will need to update the stage of the component on the ITK DB. Note that due to a bug on the ITK DB, you might also get this error if the component is not at your current location.')
    elif (('uuAppErrorMap'))[0]!='cern-itkpd-main/uploadTestRunResults/':
        output_text.set("Upload of Test Succesful!")
    else:
        output_text.set('Error!')
            
    #upload the raw data file
    if (('uuAppErrorMap')[0]!='cern-itkpd-main/uploadTestRunResults/'):
        ###Upload the attached file!
        testRun = result['testRun']['id']
        file_path = DATA_DICT['results']['FILE']
        file_name = os.path.basename(file_path)
        dataforuploadattachment={
                "testRun": testRun,
                "type": "file",
                "title": file_name, 
                "description": "Automatic Attachment of Original Data File", 
            }
        attachment = {'data': (file_name, open(file_path, 'rb'), 'text')}
        client.post("createTestRunAttachment", data = dataforuploadattachment, files = attachment)
        output_text.set("Upload of test and attachment completed.")

# GUI Definition
root = tk.Tk()
frame = tk.Frame(root, height = 600, width = 500)
frame.pack()

output_text = tk.StringVar()

db_pass_1 = tk.StringVar()
db_pass_2 = tk.StringVar()

#Define the boxes to dontain the string variables.
title = tk.Label(frame, text = 'Module Metrology Upload GUI', font = ('calibri', 18))
title.place(x = 115, y = 10 )

save_button = tk.Button(frame, text = "Save Data", command = lambda: save_data())
save_button.place(x = ENTRY_X + 110, y = ENTRY_Y + 540)

browser_button = tk.Button(frame, text = "Find File", command = lambda: get_file_data())
browser_button.place(x = ENTRY_X + 300, y = ENTRY_Y + 40)

problems_label = tk.Label(frame, text='Problems?')
problems_label.place(x = ENTRY_X + 90, y = ENTRY_Y + 380)
problems_box = tk.Listbox(frame, width = 4, relief = 'groove', height = '2')
problems_box.place(x = ENTRY_X + 150, y = ENTRY_Y + 380)
problems_box.insert(0,"Yes")
problems_box.insert(1,"No")

id_label = tk.Label(frame, text='SN')
id_label.place(x = ENTRY_X - 70, y = ENTRY_Y + 40)
id_box = tk.Text(frame, font = ('calibri', 10), width = 15, height = 1,  relief = 'sunken', state=DISABLED)
id_box.place(x = ENTRY_X - 50 , y = ENTRY_Y + 40)

run_num_label = tk.Label(frame, text='Run Number')
run_num_label.place(x = ENTRY_X - 60, y = ENTRY_Y + 410)
run_num_box = tk.Text(frame, font = ('calibri', 10), width = 8, height = 1, relief = 'sunken', state=DISABLED)
run_num_box.place(x = ENTRY_X + 15 , y = ENTRY_Y + 410)

operator_label = tk.Label(frame, text='Operator')
operator_label.place(x = ENTRY_X + 80, y = ENTRY_Y + 40)
operator_box = tk.Text(frame, font = ('calibri', 10), width = 15, height = 1, relief = 'sunken', state=DISABLED)
operator_box.place(x = ENTRY_X + 135, y = ENTRY_Y + 40)

hybrid_deviations_label = tk.Label(frame, text='Hybrid Deviations (um)')
hybrid_deviations_label.place(x = ENTRY_X - 95, y = ENTRY_Y + 80)
hybrid_deviations_box = scrolledtext.ScrolledText(frame, font = ('calibri', 10), width = 48, height = 2, relief = 'sunken',state=DISABLED)
hybrid_deviations_box.place(x = ENTRY_X + 40 , y = ENTRY_Y + 80)


pb_deviations_label = tk.Label(frame, text='Power Board Deviations (um)')
pb_deviations_label.place(x = ENTRY_X - 95, y = ENTRY_Y + 140)
pb_deviations_box = scrolledtext.ScrolledText(frame, font = ('calibri', 10), width = 44, height = 2, relief = 'sunken',state=DISABLED)
pb_deviations_box.place(x = ENTRY_X + 70, y = ENTRY_Y + 140)


cap_height_label = tk.Label(frame, text='Capacitor Heights (um)')
cap_height_label.place(x = ENTRY_X - 95, y = ENTRY_Y + 200)
cap_height_box = scrolledtext.ScrolledText(frame, font = ('calibri', 10), width = 48, height = 1, relief = 'sunken',state=DISABLED)
cap_height_box.place(x = ENTRY_X + 40, y = ENTRY_Y + 200)

hybrid_gt_label = tk.Label(frame, text='Hybrid Glue Thickness (um)')
hybrid_gt_label.place(x = ENTRY_X - 95, y = ENTRY_Y + 260)
hybrid_gt_box = scrolledtext.ScrolledText(frame, font = ('calibri', 10), width = 45, height = 2, relief = 'sunken',state=DISABLED)
hybrid_gt_box.place(x = ENTRY_X + 60, y = ENTRY_Y + 260)

pb_gt_label = tk.Label(frame, text='Power Board Glue Thickness (um)')
pb_gt_label.place(x = ENTRY_X - 95, y = ENTRY_Y + 320)
pb_gt_box = scrolledtext.ScrolledText(frame, font = ('calibri', 10), width = 41, height = 2, relief = 'sunken',state=DISABLED)
pb_gt_box.place(x = ENTRY_X + 90, y = ENTRY_Y + 320)

shield_height_label = tk.Label(frame, text='Shield Height (um)')
shield_height_label.place(x = ENTRY_X - 95, y = ENTRY_Y + 380)
shield_height_box = tk.Text(frame, font = ('calibri', 10), width = 8, height = 1, relief = 'sunken', state=DISABLED)
shield_height_box.place(x = ENTRY_X + 15, y = ENTRY_Y + 380)

db_pass_1_label = tk.Label(frame, text="AccessCode 1")
db_pass_1_label.place(x = ENTRY_X + 190, y = ENTRY_Y + 380)
db_pass_1_box = tk.Entry(frame, textvariable = db_pass_1, show='*', justify = 'left', width = 15)
db_pass_1_box.place(x = ENTRY_X + 270, y = ENTRY_Y + 380)

db_pass_2_label = tk.Label(frame, text="AccessCode 2")
db_pass_2_label.place(x = ENTRY_X + 190, y = ENTRY_Y + 410)
db_pass_2_box = tk.Entry(frame, textvariable = db_pass_2, show='*',  justify = 'left', width = 15)
db_pass_2_box.place(x = ENTRY_X + 270, y = ENTRY_Y + 410)

output_text_box = tk.Message(frame, textvariable = output_text, font = ('calibri', 10), width = 344, relief = 'sunken', justify = 'left')
output_text_box.place(x = ENTRY_X - 30, y = ENTRY_Y + 440)
output_text.set('Please enter the database serial number. Select \'Yes\' or \'No\' for if problems existed during testing.'
' Look for a data file using the \'Find File\' button to import data from an appropriate CSV.' 
'If everything looks correct press \'Save Data\' to upload to the database.' )

root.mainloop()