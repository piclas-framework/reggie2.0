## Analyze routines

|**analyze**        | **options**                          | **values**                                            |
|:-----------------:|:-------------------------------------|:------------------------------------------------------|
|L2 error           | analyze\_L2                          | 1e-5                                                  |
|h-convergence test | analyze\_Convtest\_h\_cells          | 1,2,4,8                                               |
|                   | analyze\_Convtest\_h\_tolerance      | 0.3                                                   |
|                   | analyze\_Convtest\_h\_rate           | 1.0                                                   |
|p-convergence test | analyze\_Convtest\_p\_rate           | 0.6                                                   |
|h5diff             | h5diff\_file                         | single-particle\_State\_000.00000000000000000.h5      |
|                   | h5diff\_reference\_file              | single-particle\_State\_000.00000000000000000.h5\_ref |
|                   | h5diff\_data\_set                    | DG\_Solution                                          |
|                   | h5diff\_tolerance\_value             | 1.0e-2                                                |
|                   | h5diff\_tolerance\_type              | relative                                              |
|data file line     | compare\_data\_file\_name            | Database.csv                                          |
|                   | compare\_data\_file\_reference       | Database.csv\_ref                                     |
|                   | compare\_data\_file\_tolerance       | 6e-2                                                  |
|                   | compare\_data\_file\_tolerance\_type | relative                                              |

