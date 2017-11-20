## Analyze routines

|**analyze**               | **options**                          | **values**                                            | **Devault values**               | **Desciption**           
|:------------------------:|:-------------------------------------|:------------------------------------------------------|:---------------------------------|:---------------------------------------------------------------------------------------------------------------------------|
|L2 error                  | analyze\_L2                          | 1e-5                                                  | None                             | L2 upper boundary for all nVar. If one L2 error is above the boundary, this test fails                                     |
|h-convergence test        | analyze\_Convtest\_h\_cells          | 1,2,4,8                                               | None                             | number of cells (in each direction, or in the direction of the convergence test variable)                                  |
|                          | analyze\_Convtest\_h\_tolerance      | 0.3                                                   | 0.02                             | relative deviation from the p+1 convergence rate to the calculated one                                                     |
|                          | analyze\_Convtest\_h\_rate           | 1.0                                                   | 1.0                              | ratio of successful tests versus failed tests regarding the numnber of nVar                                                |
|p-convergence test        | analyze\_Convtest\_p\_rate           | 0.6                                                   | None                             | ratio of successful tests versus failed tests regarding the numnber of nVar                                                |
|                          | analyze\_Convtest\_p\_percentage     | 0.5                                                   | 0.75                             | ratio of successful tests versus failed tests regarding the numnber of nVar                                                |
|h5diff                    | h5diff\_file                         | single-particle\_State\_000.00000000000000000.h5      | None                             | name of calculated .h5 file (output from current run)                                                                      |
|                          | h5diff\_reference\_file              | single-particle\_State\_000.00000000000000000.h5\_ref | None                             | reference .h5 file (must be placed in repository) for comparing with the calculated one                                    |
|                          | h5diff\_data\_set                    | DG\_Solution                                          | None                             | name of data set for comparing (e.g. DG\_Solution)                                                                         |
|                          | h5diff\_tolerance\_value             | 1.0e-2                                                | 1e-5                             | relative/absolute deviation between two elements in a .h5 array                                                            |
|                          | h5diff\_tolerance\_type              | relative                                              | absolute                         | relative or absolute comparison                                                                                            |
|data file line            | compare\_data\_file\_name            | Database.csv                                          | None                             | name of calculated ASCI data file (usually .csv file)                                                                      |
|                          | compare\_data\_file\_reference       | Database.csv\_ref                                     | None                             | name of reference file (must be placed inrepository)                                                                       |
|                          | compare\_data\_file\_tolerance       | 6e-2                                                  | None                             | relative/absolute deviation between two elements (in e.g. .csv file                                                        |
|                          | compare\_data\_file\_tolerance\_type | relative                                              | absolute                         | relative or absolute comparison                                                                                            |
|                          | compare\_data\_file\_line            | 50                                                    | last                             | line number in calculated data file (e.g. .csv file)                                                                       |
|integrate data column     | integrate\_line\_file                | Database.csv                                          | None                             | name of calculated output file (e.g. .csv file)                                                                            |
|                          | integrate\_line\_delimiter           | :                                                     | ,                                | delimiter symbol, default is comma ','                                                                                     |
|                          | integrate\_line\_columns             | 0:5                                                   | None                             | two columns for the values x and y supplied as 'x:y'                                                                       |
|                          | integrate\_line\_integral_value      |                                                       | None                             | integral value used for comparison                                                                                         |
|                          | integrate\_line\_tolerance_value     |                                                       | None                             | tolerance that is used in comparison                                                                                       |
|                          | integrate\_line\_tolerance_type      |                                                       | None                             | type of tolerance, either 'absolute' or 'relative'                                                                         |
|                          | integrate\_line\_option              | DivideByTimeStep                                      | None                             | special option, e.g., calculating a rate by dividing the integrated values by the timestep which is used in the values 'x' |
|                          | integrate\_line\_multiplier          | 1                                                     | 1                                | factor for multiplying the result (in order to accquire a physically meaning value for comparison)                         |

### h5diff
* Copares two arrays from two .h5 files element-by-element either with an absolute or relative difference (when comparing with zero, h5diff automatically uses an absolute comparison).  
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