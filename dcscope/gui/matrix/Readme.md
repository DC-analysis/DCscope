# The Block Matrix

Each matrix item in the block matrix has access to the `Pipeline`
object.


## Geometric Layout

This is how the individual matrix elements are organized.

|                 | MatrixFilter 1       | MatrixFilter 2       | MatrixPlot 1         | MatrixPlot 2           |
|-----------------|----------------------|----------------------|----------------------|------------------------|
| MatrixDataset A | DataMatrixElement 1A | DataMatrixElement 2A | PlotMatrixElement 1A | PlotMatrixElement 2A   |
| MatrixDataset B | DataMatrixElement 1B | DataMatrixElement 2B | PlotMatrixElement 1B | PlotMatrixElement 2B   |
| MatrixDataset C | DataMatrixElement 1C | DataMatrixElement 2C | PlotMatrixElement 1C | PlotMatrixElement 2C   |

The geometric layout is split into left (`DataMatrix`) and right (`PlotMatrix`)
parts. Each of the widgets (tiles) knows where it is located within its parent
widget (e.g. `DataMatrixElement 1A` is at row 1 and column 1).


## Qt/Signaling Hierarchy for pipeline modifications

Changes in the pipeline are sent to the parent widget (hierarchy up)
using the `pp_mod_send` signal. Changes are sent down the hierarchy
using `pp_mod_recv`. Upon receiving a signal, the widget has to make
sure that it is displaying the correct information and change itself
accordingly.

```
BlockMatrix
- DataMatrix
  - MatrixFilter 1
  - MatrixFilter 2
  - MatrixDataset A
  - DataMatrixElement 1A
  - DataMatrixElement 2A
  - MatrixDataset B
  - DataMatrixElement 1B
  - DataMatrixElement 2B
  - MatrixDataset C
  - DataMatrixElement 1C
  - DataMatrixElement 2C
- PlotMatrix
  - MatrixPlot 1
  - MatrixPlot 1
  - PlotMatrixElement 1A
  - PlotMatrixElement 2A
  - PlotMatrixElement 1B
  - PlotMatrixElement 2B
  - PlotMatrixElement 1C
  - PlotMatrixElement 2C
```

