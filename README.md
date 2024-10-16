# CK3-Locator-Checker
Compares your modded locators against reference expectation on the modded province map<br>
Extract folder from downloaded .zip anywhere you like and run CK3_locator_checker.exe<br>
Locator files with removed mismatched locators are found in new folder updated_locators after running the script

## Important
You need to manually place your edited province.png file in the script directory and name it "province_modded.png".<br>
Delete updated_locators folder everytime you re-run the script.<br>
Base game reference directory can be swapped with another mod, like Rajas of Asia.<br>

## Details

1) Script first compares definition.csv of base game and mod folder and creates new_definition.csv containing only the mismatching lines.

2) Iterate through locator files both in base game and mod folder and create big data files mapdata_base.csv and mapdata_modded.csv which contain ProvinceID;R;G;B;X;Y;ProvinceName for every locator ID (sorted for each file). the X Y coordinates are extracted from the ID and the mathematical inversion for the Y-coordinate based on province.png height applied. The R;G;B values are read directly from the province map using these coordinates, since they do not always match the ones provided in definition.csv file

3) Copy all locator files from base folder and replace/add locator IDs from mod file, based on the differences from step 1)

4) Iterate throught the updated locator files, assign each ID their R;G;B;X;Y value from the files from step 2), differentiating if the id block is from base or from mod (latter is marked with a #Modded in the updated locator file). Do another RGB check against the  provinces_modded.png map in the script directory. If the RGB matches the expectations, do nothing. If there is a mismatch, write it in a new output file and remove the ID block from the locator file, so it can be re-generated using the map tool
