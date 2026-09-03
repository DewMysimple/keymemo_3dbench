"""Read-only regression tests: edit disposable in-memory copies, never save."""
from pathlib import Path
import sys

import bmesh
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_specimen_frame_crystal_core import TARGET, OUTER, MATERIALS, validate, digest


def alter_face(obj, operation):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    face = bm.faces[-1]
    if operation == "remove":
        bmesh.ops.delete(bm, geom=[face], context="FACES")
    elif operation == "duplicate":
        bmesh.ops.duplicate(bm, geom=[face])
    elif operation == "reverse":
        face.normal_flip()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def main():
    before = digest(TARGET)
    cases = {"remove": "core_closed_six_faces", "duplicate": "no_duplicate_faces",
             "reverse": "core_normals_outward", "white_wall_purple": "face_assignments",
             "collapsed_uv": "uvs_nonzero_on_all_faces", "wrong_alpha": "material_settings"}
    bpy.ops.wm.open_mainfile(filepath=str(TARGET))
    assert validate()["checks"]["all_passed"]
    for case, expected_failure in cases.items():
        bpy.ops.wm.open_mainfile(filepath=str(TARGET))
        obj = bpy.data.objects[OUTER]
        if case in {"remove", "duplicate", "reverse"}:
            alter_face(obj, case)
        elif case == "white_wall_purple":
            obj.data.polygons[2].material_index = 1
        elif case == "collapsed_uv":
            for loop in obj.data.polygons[0].loop_indices:
                obj.data.uv_layers.active.data[loop].uv = (0, 0)
        else:
            bpy.data.materials[MATERIALS[0]].node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 1
        checks = validate()["checks"]
        assert not checks["all_passed"] and not checks[expected_failure], (case, checks)
        print("REJECTED_AS_EXPECTED=" + case)
    assert digest(TARGET) == before, "Regression test modified the delivered file."
    print("CRYSTAL_REGRESSION_TESTS=7 passed; delivered bytes unchanged")


if __name__ == "__main__":
    main()
