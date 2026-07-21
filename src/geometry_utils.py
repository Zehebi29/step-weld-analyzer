"""Geometry utilities for weld feature extraction from STEP models.

Provides functions to compute geometric properties from 
pythonocc-core (OCC) shape objects.
"""

import math
import numpy as np
from typing import List, Tuple, Optional, Dict


def bounding_box(shape) -> Tuple[float, float, float, float, float, float]:
    """Get bounding box (xmin, ymin, zmin, xmax, ymax, zmax)"""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib_Add
    
    bbox = Bnd_Box()
    brepbndlib_Add(shape, bbox)
    return bbox.Get()


def bbox_dimensions(bbox) -> Tuple[float, float, float]:
    """Get dimensions from bounding box."""
    xmin, ymin, zmin, xmax, ymax, zmax = bbox
    return (xmax - xmin, ymax - ymin, zmax - zmin)


def bbox_center(bbox) -> Tuple[float, float, float]:
    """Get center point from bounding box."""
    xmin, ymin, zmin, xmax, ymax, zmax = bbox
    return ((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)


def face_area(face) -> float:
    """Compute area of a face."""
    from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
    from OCC.Core.gp import gp_Pnt
    props = brepgprop_SurfaceProperties(face)
    return props.Mass()


def edge_length(edge) -> float:
    """Compute length of an edge."""
    from OCC.Core.BRepGProp import brepgprop_LinearProperties
    props = brepgprop_LinearProperties(edge)
    return props.Mass()


def shape_center_of_mass(shape):
    """Get center of mass of a shape."""
    from OCC.Core.BRepGProp import brepgprop_VolumeProperties
    from OCC.Core.GProp import GProp_GProps
    props = GProp_GProps()
    brepgprop_VolumeProperties(shape, props)
    cm = props.CentreOfMass()
    return (cm.X(), cm.Y(), cm.Z())


def distance_between_points(p1: Tuple[float,float,float], 
                            p2: Tuple[float,float,float]) -> float:
    """Euclidean distance between two 3D points."""
    return math.sqrt(sum((a-b)**2 for a, b in zip(p1, p2)))


def project_point_on_line(point, line_start, line_end):
    """Project a point onto a line, return the closest point and parameter t."""
    p = np.array(point)
    s = np.array(line_start)
    e = np.array(line_end)
    vec = e - s
    t = np.dot(p - s, vec) / np.dot(vec, vec)
    t = np.clip(t, 0, 1)
    proj = s + t * vec
    return tuple(proj), t


def classify_weld_joint(face1_normal, face2_normal, angle_threshold_butt=15.0):
    """Classify weld joint type based on face normals.
    
    Returns: 'butt', 'fillet', 'lap', or 'unknown'
    """
    n1 = np.array(face1_normal)
    n2 = np.array(face2_normal)
    
    # Normalize
    n1 = n1 / np.linalg.norm(n1)
    n2 = n2 / np.linalg.norm(n2)
    
    dot_product = np.dot(n1, n2)
    angle = math.degrees(math.acos(np.clip(dot_product, -1.0, 1.0)))
    
    if angle < angle_threshold_butt:
        # Normals point in similar direction → butt joint
        return 'butt'
    elif angle > 180 - angle_threshold_butt:
        # Normals point in opposite → also butt (plate edge to edge)
        return 'butt'
    elif 60 < angle < 120:
        # Normals perpendicular → fillet (T-joint / corner)
        return 'fillet'
    else:
        return 'unknown'


def estimate_weld_throat_thickness(leg_length: float, 
                                   joint_type: str = 'fillet') -> float:
    """Estimate throat thickness from leg length.
    
    For fillet welds: throat = leg_length * cos(45°) ≈ leg_length * 0.707
    For butt welds: throat ≈ plate_thickness (if full penetration)
    """
    if joint_type == 'fillet':
        return leg_length * 0.707
    else:
        return leg_length  # For butt welds, throat ≈ thickness


def weld_volume(leg_length: float, weld_length: float, 
                joint_type: str = 'fillet') -> float:
    """Estimate weld metal volume in mm³."""
    if joint_type == 'fillet':
        # Area of fillet weld cross-section = leg_length² / 2
        cross_section = (leg_length ** 2) / 2.0
    else:
        # For butt welds: cross-section ≈ thickness * gap
        cross_section = leg_length * 1.0  # rough estimate
    
    return cross_section * weld_length
