import numpy as np
from ... import AutomaticDifferentiation as ad
from ... import LinearParallel as lp
from ... import FiniteDifferences as fd
from ..base import Base


class ImplicitBase(Base):
	"""
	Base class for a metric defined implicitly, 
	in terms of a level set function for the unit ball
	of the dual metric, and of a linear transformation.
	"""

	def __init__(self,inverse_transformation=None,niter_sqp=6,relax_sqp=tuple()):
		self.inverse_transformation = inverse_transformation
		self.niter_sqp = niter_sqp
		self.relax_sqp = relax_sqp

	def norm(self,v):
		return lp.dot_VV(v,self.gradient(v))

	def gradient(self,v):
		a=self.inverse_transformation
		if a is None:
			return self._gradient(v)
		else:
			v,a = fd.common_field((v,a),(1,2))
			return lp.dot_AV(lp.transpose(a),self._gradient(lp.dot_AV(a,v)))

	def inv_transform(self,a):
		self._to_common_field(a.shape[2:])
		if self.inverse_transformation is None:
			self.inverse_transformation = a
		else:
			self.inverse_transformation = lp.dot_AA(self.inverse_transformation,a)

	def is_topographic(self,a=None):
		if a is None: a = self.inverse_transformation
		if a in None: return True
		d = self.vdim
		return np.all([a[i,j]==(i==j) for i in range(d) for j in range(d-1)])

	def flatten_transform(self,topographic=None):
		a = self.inverse_transformation
		if a is None: return None

		if topographic is None: topographic = self.is_topographic(a)
		d=self.vdim
		if topographic:
			return ad.array([a[i,-1] in range(d-1)] + [a[d-1,d-1]-1])
		else:
			return a.reshape((d*d,)+a.shape[2:])

	def _gradient(self,v):
		"""
		Gradient, ignoring self.a
		Note : modifies v where null
		"""
		v=ad.array(v)
		zeros = np.all(v==0.,axis=0)
		v[:,zeros]=np.nan
		grad = sequential_quadratic(v,self._dual_level,params=self._dual_params(v.shape[1:]),
			niter=self.niter_sqp,relax=self.relax_sqp)
		grad[:,zeros]=0.
		v[:,zeros]=0.
		return grad


	def _dual_level(self,v,params=None,relax=0):
		"""
		A level set function for the dual unit ball, ignoring self.inverse_transformation.
		Parameters
		- v : co-vector
		- params : Some parameters of the instance can be passed in argument, for AD purposes.
		- relax : for a relaxation of the level set. 0->exact, np.inf->easy (quadratic).
		"""
		raise ValueError('_dual_level is not implemented for this class')
		
	def _dual_params(self,*args,**kwargs):
		"""
		The parameters to be passed to _dual_level.
		"""
		return None

	def __iter__(self):
		yield self.inverse_transformation
		yield self.niter_sqp
		yield self.relax_sqp

	def _to_common_field(self,*args,**kwargs):
		"""Makes compatible the dimensions of the various fields"""
		raise ValueError("_to_common_field is not implemented for this class")


def sequential_quadratic(v,f,niter,x=None,params=tuple(),relax=tuple()):
	"""
	Maximizes <x,v> subject to the constraint f(x,*params)<=0, 
	using sequential quadratic programming.
	x : initial guess.
	relax : relaxation parameters to be used in a preliminary path following phase.
	params : to be passed to evaluated function. Special treatment if ad types.
	"""
	if x is None: x=np.zeros(v.shape)
	x_ad = ad.Dense2.identity(constant=x,shape_free=(len(x),))

	# Fixed point iterations 
	def step(val,V,D,v):
		M = lp.inverse(D)
		k = np.sqrt((lp.dot_VAV(V,M,V)-2.*val)/lp.dot_VAV(v,M,v))
		return lp.dot_AV(M,k*v-V)

	# Initial iterations ignoring AD information in params
	params_noad = tuple(ad.remove_ad(val) for val in params) 
	for r in relax + (0.,)*niter:
		f_ad = f(x_ad,params_noad,relax=r)
		x_ad = x_ad+step(f_ad.value,f_ad.gradient(),f_ad.hessian(),v)

	x=x_ad.value

	# Terminal iteration to introduce ad information from params
	adtype = ad.is_ad(params,iterables=(tuple,))
	if adtype:
		shape_bound = x.shape[1:]
		params_dis = tuple(ad.disassociate(value,shape_bound=shape_bound) 
			if isinstance(value,np.ndarray) else value for value in params)
		x_ad = ad.Dense2.identity(constant=ad.disassociate(x,shape_bound=shape_bound))

		f_ad = f(x_ad,params_dis,0.)
		x = x + step(ad.associate(f_ad.value), ad.associate(f_ad.gradient()), ad.associate(f_ad.hessian()), v)

	return x

