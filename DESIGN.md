# FORGE Q4 design notes

A compact quadruped presented as a precision instrument. Neutral white shell, graphite fairings, recessed shoulder joints and a dark sensor visor. Real lofted CAD geometry carries the silhouette; surface finish in the renderer does not assert a carbon-composite material specification.

Palette: black `#000000`, charcoal `#0c0c0c`, graphite `#333333`, neutral grey `#929292`, porcelain `#f2f2f0`, white `#ffffff`. Neutral lights, system sans typography, tabular measurements. The studio uses a dark stage and quiet controls. The CAD desk uses white A3 sheets with precise black linework.

The drawing desk exposes twelve part definitions, assembly / exploded sheets, a 42-instance BOM, real BREP measurements, construction recipes and the parameters supported by the compiler. Editing separates proposed parameters from committed geometry. Exports are disabled until the kernel produces a valid matching revision.

The operation list describes the Python construction recipe. It is not an editable native CAD feature-history tree. The engineering sheets use OCCT hidden-line projection and BREP sections. Display curves are sampled; DXF exports projected CAD edges and STEP carries the solids. Manufacturing tolerances and device internals remain outside this concept's scope.

Motion studio adds a white control rail with three motion groups, a large dark object stage, contact timing and a collapsible joint inspector. Controls reserve space for the robot's feet; on narrow screens the inspector moves below the stage. Fifteen choreographies share the actual CAD link dimensions and a three-joint-per-leg inverse-kinematics solver. Body and foot targets blend through the solver rather than moving disconnected meshes. The fixed foot remains attached to the lower link. Joint readouts explicitly show offsets from CAD home, and exports label their scope as kinematic preview rather than hardware control or physical simulation.

The trailer uses forty hard-cut scenes over sixty seconds. Fixed framing avoids animated scaling of captured pixels. Public media contains only the finished cropped trailer and poster; source desktop recordings stay local.

The engineering workspace adds a distinct physics engine selector, actual normal-force cells, IMU and torque/work readouts, force trails and a restrained contact grid. The floating robot comes from MuJoCo body transforms; the renderer applies no prescribed base motion. Force arrows and CoM are measurement overlays. Reference footfall timing is labelled as a command schedule. The CAD fairing termination and 32 mm foot pad were revised after physical contacts exposed metal touching the floor first.

AI Engineering là bàn làm việc toàn màn hình sáng, với cột proposal/đo lường và baseline ở cạnh. Modal dừng render GPU phía sau; nguồn chân lý vẫn là spec/revision. Kết quả so sánh hiển thị cả lỗi và tiêu chí khai báo. Mô hình vận hành phân biệt lực/góc giải thực với điện/nhiệt ước tính; mobile giữ ba chỉ báo vận hành chính để dành chỗ cho robot.
