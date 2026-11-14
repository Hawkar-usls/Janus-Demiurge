#!/usr/bin/env python3
"""Independent Einstein 3+1 algebra, Alcubierre radial budget, causal caveats."""
import math
import unittest

import alcubierre_einstein_011g as a

class AlcubierreEinsteinTests(unittest.TestCase):
    def test_original_profile_center_and_far_flat(self):
        for R,delta in ((100.,10.),(10.,1.),(100.,1.)):
            self.assertAlmostEqual(a.shape_f(0,R,delta),1.,places=13)
            self.assertLess(a.shape_f(R+20*delta,R,delta),1e-15)
            self.assertAlmostEqual(a.df_dr(0,R,delta),0.,places=14)

    def test_exact_ADM_hamiltonian_algebra(self):
        # Shift beta_x=-v f. Kxx=-v fx; Kxy=-v fy/2; Kxz=-v fz/2.
        v,fx,fy,fz=0.8,0.21,-0.44,0.12
        K_trace=-v*fx
        Kij_square=(v*fx)**2+2*(v*fy/2)**2+2*(v*fz/2)**2
        Einstein_constraint=K_trace**2-Kij_square
        predicted=-(v*v/2)*(fy*fy+fz*fz)
        self.assertAlmostEqual(Einstein_constraint,predicted,places=14)
        # Geometric energy = ADM / (16 pi), exactly negative except on axis.
        self.assertLess(Einstein_constraint/(16*math.pi),0)

    def test_integrand_nonnegative_negative_energy_sign(self):
        for R,delta in ((100.,10.),(100.,1.),(10.,1.)):
            i=a.simpson_integral(R,delta,2000)
            self.assertGreater(i,0)
            self.assertLess(a.energy_from_integral(i,.1),0)
        self.assertEqual(a.energy_from_integral(10.,0.),0)

    def test_velocity_squared_scaling_independent_of_quadrature(self):
        I=a.simpson_integral(100.,10.,4000)
        self.assertAlmostEqual(a.energy_from_integral(I,2.)/a.energy_from_integral(I,1.),4.)
        self.assertAlmostEqual(a.energy_from_integral(I,.1)/a.energy_from_integral(I,1.),.01)

    def test_wall_toroidal_density_is_zero_on_x_axis(self):
        equator=a.wall_density(100.,10.,1.,math.pi/2)
        axis=a.wall_density(100.,10.,1.,0.)
        self.assertLess(equator,0)
        self.assertEqual(axis,0)
        self.assertAlmostEqual(a.wall_density(100.,10.,2.)/equator,4.)

    def test_energy_is_extremely_large_but_only_a_model(self):
        val=a.case(100.,10.,1.)
        self.assertGreater(val["negative_energy_magnitude_J"],1e44)
        self.assertLess(val["negative_energy_magnitude_J"],1e47)
        self.assertGreater(val["negative_energy_magnitude_mass_equivalent_earth_masses"],100)
        self.assertFalse(val["physically_existent_negative_energy_source_supplied"])
        self.assertFalse(val["source_stress_energy_tensor_fully_constructed"])

    def test_radial_convergence_and_wall_scaling(self):
        val=a.case(100.,10.,1.)
        self.assertLess(val["radial_numerical_relative_convergence"],1e-5)
        thin=a.case(100.,1.,1.)
        self.assertLess(thin["coordinate_slice_integrated_local_energy_J"],
                        val["coordinate_slice_integrated_local_energy_J"])
        # thin wall I ~R²/(3 Delta), the relative difference shrinks for R/Delta=100.
        self.assertLess(abs(thin["approximation_relative_error"]),.002)

    def test_radius_scale_at_constant_relative_wall(self):
        small=a.case(10.,1.,1.)
        big=a.case(100.,10.,1.)
        ratio=big["negative_energy_magnitude_J"]/small["negative_energy_magnitude_J"]
        self.assertAlmostEqual(ratio,10.,delta=0.001)

    def test_superluminal_axis_root_only_a_coordinate_stagnation(self):
        self.assertIsNone(a.possible_forward_axis_horizon(100.,10.,1.))
        self.assertIsNone(a.possible_forward_axis_horizon(100.,10.,.1))
        q=a.possible_forward_axis_horizon(100.,10.,2.)
        self.assertAlmostEqual(q["f_shape_at_zero_coordinate_outgoing_speed"],.5,places=9)
        self.assertLess(abs(q["forward_ray_comoving_speed_m_per_s"]),1e-6)
        self.assertTrue(80<q["positive_x_axis_r_m"]<120)
        self.assertIn("NOT global",q["strict_status"])

    def test_invalid_shapes_and_simpson_fail_closed(self):
        for args in ((-1.,10.,1.),(100.,0.,1.),(100.,10.,-1.)):
            with self.assertRaisesRegex(ValueError,"R_POSITIVE"):
                a.case(*args)
        with self.assertRaisesRegex(ValueError,"EVEN_SIMPSON"):
            a.simpson_integral(100.,10.,9)
        with self.assertRaisesRegex(ValueError,"RADIUS_NONNEGATIVE"):
            a.shape_f(-1.,100.,10.)
        with self.assertRaisesRegex(ValueError,"FINITE"):
            a.case(100.,10.,float("nan"))

    def test_no_false_retrocausal_admission(self):
        r=a.evaluate()
        self.assertFalse(r["physical_and_temporal_admission"]["retrocausality_proven"])
        self.assertEqual(r["physical_and_temporal_admission"]["external_lab_trials"],0)
        self.assertFalse(r["physical_and_temporal_admission"]["genuine_closed_timelike_curve_constructed"])
        self.assertTrue(r["physical_and_temporal_admission"]["negative_energy_density_in_this_metric_required"])
        self.assertFalse(r["Einstein_3plus1_Hamiltonian_derivation"]["full_Einstein_tensor_or_realistic_matter_model_constructed"])

if __name__=="__main__":
    unittest.main()
