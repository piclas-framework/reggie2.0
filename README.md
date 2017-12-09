# Table of Contents
1. [Analyze routines overview](#analyze-routines)
2. [L2 error](#l2-error)
3. [h-convergence test](#h-convergence-test)
4. [p-convergence test](#p-convergence-test)
5. [h5diff](#h5diff)
6. [h5 array bounds check](#h5-array-bounds-check)
7. [Data file line comparison](#data-file-line-comparison)
8. [integrate data columns](#integrate-data-columns)

# Analyze routines

|**analyze**               | **options**                          | **values**                                            | **Devault values**               | **Description**           
|:------------------------:|:-------------------------------------|:------------------------------------------------------|:---------------------------------|:---------------------------------------------------------------------------------------------------------------------------|
|L2 error                  | analyze\_L2                          | 1e-5                                                  | None                             | L2 upper boundary for all nVar. If one L2 error is above the boundary, this test fails                                     |
|h-convergence test        | analyze\_Convtest\_h\_cells          | 1,2,4,8                                               | None                             | number of cells (in each direction, or in the direction of the convergence test variable)                                  |
|                          | analyze\_Convtest\_h\_tolerance      | 0.3                                                   | 0.02                             | relative deviation from the p+1 convergence rate to the calculated one                                                     |
|                          | analyze\_Convtest\_h\_rate           | 1.0                                                   | 1.0                              | ratio of successful tests versus failed tests regarding the number of nVar                                                 |
|p-convergence test        | analyze\_Convtest\_p\_rate           | 0.6                                                   | None                             | ratio of successful tests versus failed tests regarding the number of nVar                                                 |
|                          | analyze\_Convtest\_p\_percentage     | 0.5                                                   | 0.75                             | ratio of successful tests versus failed tests regarding the number of nVar                                                 |
|h5diff                    | h5diff\_file                         | single-particle\_State\_000.00000000000000000.h5      | None                             | name of calculated .h5 file (output from current run)                                                                      |
|                          | h5diff\_reference\_file              | single-particle\_State\_000.00000000000000000.h5\_ref | None                             | reference .h5 file (must be placed in repository) for comparing with the calculated one                                    |
|                          | h5diff\_data\_set                    | DG\_Solution                                          | None                             | name of data set for comparing (e.g. DG\_Solution)                                                                         |
|                          | h5diff\_tolerance\_value             | 1.0e-2                                                | 1e-5                             | relative/absolute deviation between two elements in a .h5 array                                                            |
|                          | h5diff\_tolerance\_type              | relative                                              | absolute                         | relative or absolute comparison                                                                                            |
|h5 array bounds check     | check\_hdf5\_file                    | tildbox_State_001.00000000000000000.h5                | None                             | name of calculated .h5 file (output from current run)                                                                      |
|                          | check\_hdf5\_data\_set               | PartData                                              | None                             | name of data set for comparing (e.g. DG\_Solution)                                                                         |
|                          | check\_hdf5\_dimension               | 0:2                                                   | None                             | dimension of data set                                                                                                      |
|                          | check\_hdf5\_limits                  | -10.0:10.0                                            | None                             | bounding interval for all elements in h5 array for all dimensions supplied under check\_hdf5\_dimension                    |
|data file line            | compare\_data\_file\_name            | Database.csv                                          | None                             | name of calculated ASCII data file (usually .csv file)                                                                     |
|                          | compare\_data\_file\_reference       | Database.csv\_ref                                     | None                             | name of reference file (must be placed in repository)                                                                      |
|                          | compare\_data\_file\_tolerance       | 6e-2                                                  | None                             | relative/absolute deviation between two elements (in e.g. .csv file                                                        |
|                          | compare\_data\_file\_tolerance\_type | relative                                              | absolute                         | relative or absolute comparison                                                                                            |
|                          | compare\_data\_file\_line            | 50                                                    | last                             | line number in calculated data file (e.g. .csv file)                                                                       |
|integrate data columns    | integrate\_line\_file                | Database.csv                                          | None                             | name of calculated output file (e.g. .csv file)                                                                            |
|                          | integrate\_line\_delimiter           | :                                                     | ,                                | delimiter symbol, default is comma ',' (note that a comma cannot be supplied in this file as it is a delimiter itself)     |
|                          | integrate\_line\_columns             | 0:5                                                   | None                             | two columns for the values x and y supplied as 'x:y'                                                                       |
|                          | integrate\_line\_integral_value      | 44.00                                                 | None                             | integral value used for comparison                                                                                         |
|                          | integrate\_line\_tolerance_value     | 0.8e-2                                                | None                             | tolerance that is used in comparison                                                                                       |
|                          | integrate\_line\_tolerance_type      | relative                                              | None                             | type of tolerance, either 'absolute' or 'relative'                                                                         |
|                          | integrate\_line\_option              | DivideByTimeStep                                      | None                             | special option, e.g., calculating a rate by dividing the integrated values by the timestep which is used in the values 'x' |
|                          | integrate\_line\_multiplier          | 1                                                     | 1                                | factor for multiplying the result (in order to acquire a physically meaning value for comparison)                          |

# L2 error
* Compare all L2 errors calculated for all nVar against an upper boundary *analyze_L2*

Template for copying to **analyze.ini**

```
!L2 error norm
analyze_L2=1e7
```

# h-convergence test
* Determine the rate of convergence versus decreasing the average spacing between two DOF by running multiple different grids
* Requires multiple mesh files

Template for copying to **analyze.ini**

```
! h-convergence test
analyze_Convtest_h_cells=1,2,4,8
analyze_Convtest_h_tolerance=0.3
analyze_Convtest_h_rate=1
```

# p-convergence test
* Determine an increasing rate of convergence by increasing the polynomial degree (for a constant mesh)

Template for copying to **analyze.ini**

```
! p-convergence test
analyze_Convtest_p_rate=0.8
analyze_Convtest_p_percentage=0.75
```

# h5diff
* Compares two arrays from two .h5 files element-by-element either with an absolute or relative difference (when comparing with zero, h5diff automatically uses an absolute comparison).  
* Requires h5diff, which is compiled within the HDF5 package.  

Template for copying to **analyze.ini**

```
! hdf5 diff
h5diff_file            =          single-particle_State_000.00000005000000000.h5
h5diff_reference_file  = single-particle_reference_State_000.0000000500000000.h5
h5diff_data_set        = DG_Source
h5diff_tolerance_value = 1.0e-2
h5diff_tolerance_type  = relative
```

# h5 array bounds check
* Check if all elements of a h5 array are within a supplied interval
* Requires *h5py* python module (analyze will fail if the module cannot be found)

Template for copying to **analyze.ini**

```
! check if particles are outside of domain at tEnd
check_hdf5_file        = tildbox_State_001.00000000000000000.h5
check_hdf5_data_set    = PartData
check_hdf5_dimension   = 0:2
check_hdf5_limits      = -10.0:10.0
```

# Data file line comparison
* Compare a live in, e.g., a .csv file element-by-elements
* relative of absolute comparison

### Example 1 of 3
Template for copying to **analyze.ini**

```
! compare the last row in Database.csv with a reference file
compare_data_file_name      = Database.csv
compare_data_file_reference = Database_reference.csv
compare_data_file_tolerance = 2.0
compare_data_file_tolerance_type = relative
```
### Example 2 of 3

When different runs produce different output (e.g. changing the initial conditions, here, the temperature is varied), multiple reference files can be supplied. The following example produces the same output file (Database.csv) but compares with different reference files (Database\_TX000K\_ref.csv).

```
! compare the last row in Database.csv with a reference file
compare_data_file_name      = Database.csv
compare_data_file_reference = Database_T1000K_ref.csv, Database_T2000K_ref.csv, Database_T3000K_ref.csv, Database_T4000K_ref.csv, Database_T5000K_ref.csv
compare_data_file_tolerance = 2.0
compare_data_file_tolerance_type = relative
```
### Example 3 of 3

Additionally, multiple output files (Database\_TX000K.csv) can be supplied in combination with multiple reference files (Database\_TX000K\_ref.csv). See the following example. 

```
! compare the last row in Database.csv with a reference file
compare_data_file_name      = Database_T1000K.csv, Database_T2000K.csv, Database_T3000K.csv, Database_T4000K.csv, Database_T5000K.csv
compare_data_file_reference = Database_T1000K_ref.csv, Database_T2000K_ref.csv, Database_T3000K_ref.csv, Database_T4000K_ref.csv, Database_T5000K_ref.csv
compare_data_file_tolerance = 2.0
compare_data_file_tolerance_type = relative
```

Note that for the last example, the number of supplied output files, reference files and runs must be the same.

# integrate data columns
* Integrate the data in a column over another column, e.g., x:y in a data file as integral(y(x), x, x(1), x(end)) via the trapezoid rule
* special options are available for calculating, e.g., rates (something per second)

Template for copying to **analyze.ini**

```
! ===================================================================================================================
! integrate columns x:y in a data file as integral(y(x), x, x(1), x(end))
! check the emission current of electrons: Current = Q*MPF*q/delta_t_database = 44 A
! ===================================================================================================================
! with   Q = integrate nPartIn(t) from t=0 to t=3E-11 = 4.500111958051274e-10 for p=9 (integrate nPartIN over time)
!      MPF = 1e6
!        q = 1.6022e-19 (charge of one electron)
!       dt = ? (depends on polynomial degree and mesh)
! ===================================================================================================================
! for p = 9: 551 timesteps  -->  0.44769549409291E-09*IntegrateLineMultiplier = 44 A
integrate_line_file            = Database.csv          ! data file name
integrate_line_columns         = 0:5                   ! columns x:y
integrate_line_integral_value  = 44.00                 ! Ampere
integrate_line_tolerance_value = 0.8e-2                ! tolerance
integrate_line_tolerance_type  = relative              ! special option
integrate_line_option          = DivideByTimeStep      ! the first column in Database.csv is used for this option
integrate_line_multiplier      = 5.340588433333334e-03 ! = MPF*q/tend = 1e6*1.60217653E-19/3E-11
```

Note that a comma is the default delimiter symbol for "integrate\_line\_delimiter" and cannot be set as custom delimiter symbol "," because the comma is used for splitting the keywords in analyze.ini. However, other symbols can be supplied using "integrate\_line\_delimiter" instead of a comma.





# template
* 

Template for copying to **analyze.ini**

```
 
```