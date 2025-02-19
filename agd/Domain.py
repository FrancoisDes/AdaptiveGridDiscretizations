from . import FiniteDifferences as fd
from . import AutomaticDifferentiation as ad
from . import LinearParallel as lp

import numpy as np
from functools import reduce
from itertools import cycle

class Domain(object):
	"""
	This class represents a domain from which one can query 
	a level set function, the boundary distance in a given direction,
	and some related methods.
	"""

	def __init__(self):
		s2 = np.sqrt(2.)
		self.pattern_ball = np.stack([[1.,0.],[s2,s2],[0.,1.],[-s2,s2],
			[-1.,0.],[-s2,-s2],[0.,-1.],[s2,-s2]],axis=1)

	def level(self,x):
		"""
		A level set function, negative inside the domain, positive outside.
		Guaranteed to be 1-Lipschitz.
		"""
		raise ValueError("""Domain level set function must be specialized""")

	def contains(self,x):
		"""
		Wether x lies inside the domain.
		"""
		return self.level(x)<0

	def intervals(self,x,v):
		"""
		A union of disjoint intervals, sorted in increasing order, such 
		] a[0],b[0] [ U ] a[1],b[1] [ U ... U ] a[n-1],b[n-1] [
		such that x+h*v lies in the domain iff t lies on one of these intervals.
		"""
		raise ValueError("""Domain intervals function must be specialized""")

	def freeway(self,x,v):
		"""
		Output : Least h>=0 such that x+h*v intersects the boundary.
		"""
		a,b = self.intervals(x,v)
		a[a<0]=np.inf
		b[b<0]=np.inf
		return np.minimum(a.min(axis=0),b.min(axis=0))

	def contains_ball(self,x,h):
		if h==0.: 	return self.contains(x)
		if h<0.:	return AbsoluteComplement(self).contains_ball(x,-h)
		level = self.level(x)
		inside = level<0

		# Fix boundary layer
		mask = np.logical_and(inside,level>-h) # Recall level is 1-Lipschitz
		xm=x[:,mask]
		ball_pattern = fd.as_field(self.pattern_ball,xm.shape[1:],conditional=False)
		xb = np.expand_dims(xm,axis=1)+h*ball_pattern
		inside[mask] = np.all(self.contains(xb),axis=0)
		return inside

class WholeSpace(Domain):
	"""
	This class represents the full space R^d.
	"""
	def level(self,x):
		return np.full(x.shape[1:],-np.inf)

	def intervals(self,x,v):
		shape = (1,)+x.shape[1:]
		return np.full(shape,-np.inf),np.full(shape,np.inf)

class Ball(Domain):
	"""
	This class represents a ball shaped domain
	"""

	def __init__(self,center=(0.,0.),radius=1.):
		super(Ball,self).__init__()
		self.center = ad.toarray(center)
		self.radius = radius

	def _centered(self,x):
		_center = fd.as_field(self.center,x.shape[1:],conditional=False)
		return x-_center

	def level(self,x):
		_x = self._centered(x)
		return ad.Optimization.norm(_x,ord=2,axis=0)-self.radius

	def intervals(self,x,v):
		if v.shape!=x.shape: v=fd.as_field(v,x.shape[1:],conditional=False)
		xc = self._centered(x)

		begin = np.full(x.shape[1:],np.inf)
		end = begin.copy()

		# Solve |x+hv|^2=r, which is a quadratic equation a h^2 + 2 b h + c =0
		a = lp.dot_VV(v,v)
		b = lp.dot_VV(xc,v)
		c = lp.dot_VV(xc,xc)-self.radius

		delta = b*b-a*c

		pos = np.logical_and(a>0,delta>0)
		a,b,delta = (e[pos] for e in (a,b,delta))

		sdelta = np.sqrt(delta)
		begin[pos] = (-b-sdelta)/a
		end[pos] = (-b+sdelta)/a

		begin,end = (np.expand_dims(e,axis=0) for e in (begin,end))
		return begin,end

class Box(Domain):
	"""
	This class represents a box shaped domain.
	"""

	def __init__(self,sides = ((0.,1.),(0.,1.)) ):
		super(Box,self).__init__()
		if not isinstance(sides,np.ndarray): sides=np.array(sides)
		self._sides = sides
		self._center = sides.sum(axis=1)/2.
		self._hlen = (sides[:,1]-sides[:,0])/2.

	@property
	def sides(self): return self._sides
	@property
	def center(self): return self._center
	@property
	def edgelengths(self): return 2.*self._hlen

	def _centered(self,x,signs=False):
		center = fd.as_field(self.center,x.shape[1:],conditional=False)
		xc = x-center
		return (np.abs(xc),np.sign(xc)) if signs else np.abs(xc)


	def level(self,x):
		hlen = fd.as_field(self._hlen,x.shape[1:],conditional=False)
		return (self._centered(x) - hlen).max(axis=0)

	def intervals(self,x,v):
		shape = x.shape[1:]
		if v.shape!=x.shape: v=fd.as_field(v,shape,conditional=False)
		hlen = fd.as_field(self._hlen,shape,conditional=False)
		xc,signs = self._centered(x,signs=True)
		vc = v*signs

		a=np.full(x.shape,-np.inf)
		b=np.full(x.shape, np.inf)

		# Compute the interval corresponding to each axis
		pos = vc!=0
		hlen_,xc_,vc_ = (e[pos] for e in (hlen,xc,vc))

		a[pos] = (-hlen_-xc_)/vc_
		b[pos] = ( hlen_-xc_)/vc_

		# Deal with offsets parallel to axes
		pos = np.logical_and(vc==0.,np.abs(xc)>hlen)
		a[pos] = np.inf 

		# Intersect intervals corresponding to different axes

		a,b = np.minimum(a,b),np.maximum(a,b)
		a,b = a.max(axis=0),b.min(axis=0)
		a,b = (ad.toarray(e) for e in (a,b)) 

		# Normalize empty intervals
		pos = a>b
		a[pos]=np.inf
		b[pos]=np.inf
		a,b = (np.expand_dims(e,axis=0) for e in (a,b))
		return a,b

class AbsoluteComplement(Domain):
	"""
	This class represents the complement, in the entire space R^d, of an existing domain.
	"""
	def __init__(self,dom):
		super(AbsoluteComplement,self).__init__()
		self.dom = dom

	def contains(self,x):
		return np.logical_not(self.dom.contains(x))
	def level(self,x):
		return -self.dom.level(x)
	def freeway(self,x,v):
		return self.dom.freeway(x,v)
	def intervals(self,x,v):
		a,b = self.dom.intervals(x,v)
		inf = np.full((1,)+x.shape[1:],np.inf)
		return np.concatenate((-inf,b),axis=0),np.concatenate((a,inf),axis=0)


class Intersection(Domain):
	"""
	This class represents an intersection of several subdomains.
	"""
	def __init__(self,*doms):
		super(Intersection,self).__init__()
		self.doms=doms

	def contains(self,x):
		containss = [dom.contains(x) for dom in self.doms]
		return reduce(np.logical_and,containss)

	def level(self,x):
		levels = [dom.level(x) for dom in self.doms]
		return reduce(np.maximum,levels)

	def intervals(self,x,v):
		intervalss = [dom.intervals(x,v) for dom in self.doms]
		begs = [a for a,b in intervalss]
		ends = [b for a,b in intervalss]

		# Shortcut for the convex case, quite common
		if all(len(a)==1 for a,b in intervalss):
			beg = reduce(np.maximum,begs)
			end = reduce(np.minimum,ends)
			pos = beg>end
			beg[pos]=np.inf
			end[pos]=np.inf
			return beg,end

		# General non-convex case
		shape = x.shape[1:]

		# Prepare the result
		begr = []
		endr = []
		val = np.full(shape,-np.inf)
		inds = np.full( (len(self.doms),)+x.shape[1:], 0)
		
		def tax(arr,ind,valid):
			return np.squeeze(np.take_along_axis(arr[:,valid],np.expand_dims(ind[valid],axis=0),axis=0),axis=0)

		counter=0
		while True:
			# Find the next beginning
			unchanged=0
			for it,(beg,end) in cycle(enumerate(zip(begs,ends))):
				ind=ad.toarray(inds[it])
				valid = ind<len(end)
				pos = np.full(shape,False)
				endiv = tax(end,ind,valid)
				pos[valid] = np.logical_and(val[valid]>=endiv,endiv!=np.inf)

				if pos.any():	
					unchanged=0
				else:			
					unchanged+=1
					if unchanged>=len(begs):
						break

				inds[it,pos]+=1; ind=inds[it] 
				valid = ind<len(end)
				val[valid] = np.maximum(val[valid],tax(beg,ind,valid))
				val[np.logical_not(valid)]=np.inf

				counter+=1
				assert(counter<=100)

			#Exit if nobody's valid
			if (val==np.inf).all():
				break
			begr.append(val)

			# Find the next end
			val=np.full(shape,np.inf)
			for end,ind in zip(ends,inds):
				valid = ind<len(end)
				val[valid] = np.minimum(val[valid],tax(end,ind,valid))

			endr.append(val.copy())

		return np.array(begr),np.array(endr)
	
def Complement(dom1,dom2):
	"""
	Relative complement dom1 \\ dom2
	"""
	return Intersection(dom1,AbsoluteComplement(dom2))

def Union(*doms):
	"""
	Union of several domains.
	"""
	return AbsoluteComplement(Intersection(*[AbsoluteComplement(dom) for dom in doms]))

class Band(Domain):
	"""
	Defines a banded domain in space, in between two parallel hyperplanes.
	bounds[0] < <x,direction> < bounds[1]
	"""

	def __init__(self,direction,bounds):
		super(Band,self).__init__()
		self.direction,self.bounds = (ad.toarray(e) for e in (direction,bounds))
		norm = ad.Optimization.norm(self.direction,ord=2)
		if norm!=0.:
			self.direction/=norm
			self.bounds/=norm

	def _dotdir(self,x):
		direction = fd.as_field(self.direction,x.shape[1:],conditional=False)
		return lp.dot_VV(x,direction)

	def level(self,x):
		xd = self._dotdir(x)
		return np.maximum(self.bounds[0]-xd,xd-self.bounds[1])

	def intervals(self,x,v):
		xd = self._dotdir(x)
		vd = self._dotdir(v)
		vd = fd.as_field(vd,xd.shape)
		a = np.full(xd.shape,-np.inf)
		b = np.full(xd.shape, np.inf)

		# Non degenerate case
		mask = vd!=0
		xdm,vdm = xd[mask],vd[mask]
		a[mask] = (self.bounds[0]-xdm)/vdm
		b[mask] = (self.bounds[1]-xdm)/vdm
		# Handle the case where vd=0
		inside = np.logical_and(self.bounds[0]<xd,xd<self.bounds[1])
		a[np.logical_and(vd==0,np.logical_not(inside))]=np.inf

		a,b = np.minimum(a,b),np.maximum(a,b)
		a,b = (np.expand_dims(e,axis=0) for e in (a,b))
		return a,b

def ConvexPolygon(pts):
	"""
	Defines a convex polygonal domain from its vertices, given in trigonometric order.
	"""
	def params(p,q):
		pq = q-p
		direction = np.array([pq[1],-pq[0]])
		lower_bound = np.dot(direction,p)
		return direction,[lower_bound,np.inf]
	pts = ad.toarray(pts)
	assert len(pts)==2
	return Intersection(*[Band(*params(p,q)) for p,q in zip(pts.T,np.roll(pts,1,axis=1).T)])

class AffineTransform(Domain):
	"""
	Defines a domain which is the transformation of another domain
	by an affine transformation, 
		x' = mult x + shift
	Inputs : 
	- mult, scalar, matrix, or None (Eq 1.)
	- shift, vector, or None (Eq null vector)
	"""

	def __init__(self,dom,mult=None,shift=None,center=None):
		super(AffineTransform,self).__init__()
		self.dom=dom
		if mult is not None: mult = ad.toarray(mult)
		self._mult = mult

		if shift is not None: shift = ad.toarray(shift)
		if center is not None:
			center=ad.toarray(center)
			shift2=center-self.forward(center,linear=True)
			shift = shift2 if shift is None else shift+shift2

		self._shift = shift
		self._mult_inv = (None if mult is None else 
			(ad.toarray(1./mult) if mult.ndim==0 else np.linalg.inv(mult) ) )
		self._mult_inv_norm = (1. if self._mult_inv is None 
			else np.linalg.norm(self._mult_inv,ord=2) )

	def forward(self,x,linear=False):
		"""
		Forward affine transformation, from the original domain to the transformed one.
		"""
		x=x.copy()
		shape = x.shape[1:]

		mult = self._mult
		if mult is None: 	pass
		elif mult.ndim==0:	x*=mult
		else: x=lp.dot_AV(fd.as_field(mult,shape,conditional=False),x)

		if not linear and self._shift is not None:
			x+=fd.as_field(shift,shape,conditional=False)
		
		return x

	def reverse(self,x,linear=False):
		"""
		Reverse affine transformation, from the transformed domain to the original one.
		"""
		x=x.copy()
		shape = x.shape[1:]

		shift = self._shift
		if (shift is None) or linear: 	pass
		else:	x-=fd.as_field(shift,shape,conditional=False)

		mult = self._mult_inv
		if mult is None: 	pass
		elif mult.ndim==0:	x*=mult
		else: x = lp.dot_AV(fd.as_field(mult,shape,conditional=False),x)

		return x

	def contains(self,x):
		return self.dom.contains(self.reverse(x))
	def level(self,x):
		return self.dom.level(self.reverse(x))/self._mult_inv_norm
	def intervals(self,x,v):
		return self.dom.intervals(self.reverse(x),self.reverse(v,linear=True))
	def freeway(self,x,v):
		return self.dom.freeway(self.reverse(x),self.reverse(v,linear=True))

class Dirichlet(object):
	"""
	Implements Dirichlet boundary conditions.
	When computing finite differences, values queried outside the domain interior
	are replaced with values obtained on the boundary along the given direction.
	"""

	def __init__(self,domain,value,grid,
		interior_radius=None,interior=None,grid_values=0.):
		"""
		Domain, boundary conditions.
		Inputs:
		- domain: geometrical description of the domain 
		- value: a scalar or map yielding the value of the boundary conditions
		- grid: the cartesian grid. Ex: np.array(np.meshgrid(aX,aY,indexing='ij')) for suitable aX,aY

		- interior (optional): the points regarded as interior to the domain. 
		- interior_radius (optional): sets
			interior = domain.contains_ball(interior_radius)

		- grid_values (defaults to 0.): placeholder values to be used on the grid
		"""
		self.domain = domain

		if isinstance(value,float):
			self.value = lambda x:value
		else:
			self.value = value

		self.grid = ad.toarray(grid)
		self.gridscale = self._gridscale(self.grid)

		if interior is not None:
			self.interior = interior
		else:
			if interior_radius is None:
#				interior_radius = 0.5 * self.gridscale
				interior_radius = self.gridscale * 1e-8 # Tiny value, for numerical stability. Ideally 0.
			self.interior = self.domain.contains_ball(self.grid,interior_radius)

		if isinstance(grid_values,float) or isinstance(grid_values,np.ndarray):
			self.grid_values = grid_values
		else:
			self.grid_values = grid_values(self.grid)

	
	@staticmethod
	def _gridscale(grid):
		dim = len(grid)
		assert(grid.ndim==1+dim)
		x0 = grid.__getitem__((slice(None),)+(0,)*dim)
		x1 = grid.__getitem__((slice(None),)+(1,)*dim)
		delta = np.abs(x1-x0)
		hmin,hmax = np.min(delta),np.max(delta)
		if hmax>=hmin*(1+1e-8):
			raise ValueError("Error : gridscale is axis dependent")
		return hmax

	@property 
	def shape(self): 
		return self.grid.shape[1:]
	
	def as_field(self,arr,conditional=True):
		return fd.as_field(arr,self.shape,conditional=conditional)

	@property
	def not_interior(self):
		return np.logical_not(self.interior)
	
	@property
	def Mock(self):
		"""
		Returns mock Dirichlet boundary conditions obtained by evaluating 
		the boundary condition outside the interior.
		"""
		bc_values = np.full(self.grid.shape[1:],np.nan)
		bc_values[self.not_interior] = self.value(self.grid[:,self.not_interior])
		return MockDirichlet(bc_values,self.gridscale)

	@property
	def _ExteriorNaNs(self):
		result = np.zeros(self.grid.shape[1:])
		result[self.not_interior]=np.nan
		return result

	def _BoundaryLayer(self,u,du):
		"""
		Returns positions at which u is defined but du is not.
		"""
		return np.logical_and.reduce([
			np.isnan(du),
			np.broadcast_to(self.interior,du.shape),
			np.broadcast_to(np.logical_not(np.isnan(u)),du.shape)
			])

	def _DiffUpwindDirichlet(self,u,offsets,grid,reth):
		"""
		Returns first order finite differences w.r.t. boundary value.
		"""
		h = self.domain.freeway(grid,offsets)
		x = grid+h*offsets
		xvalues = self.value(x)
		result = (xvalues-u)/h
		return (result,h) if reth else result



	def DiffUpwind(self,u,offsets,reth=False):
		"""
		Returns first order finite differences, uses boundary values when needed.
		"""
		assert(isinstance(reth,bool))
		grid=self.grid
		du = fd.DiffUpwind(u+self._ExteriorNaNs,offsets,self.gridscale)
		mask = self._BoundaryLayer(u,du)
		offsets = fd.as_field(np.array(offsets),u.shape)
		um = ad.broadcast_to(u,offsets.shape[1:])[mask]
		om = offsets[:,mask]
		gm = ad.broadcast_to(grid.reshape( (len(grid),)+(1,)*(offsets.ndim-grid.ndim)+u.shape),offsets.shape)[:,mask]
#		um,om,gm = u[mask], offsets[:,mask], grid[:,mask]
		if not reth: 
			du[mask] = self._DiffUpwindDirichlet(um,om,gm,reth=reth)
			return du
		else: 
			hr = np.full(offsets.shape[1:],self.gridscale)
			du[mask],hr[mask] = self._DiffUpwindDirichlet(um,om,gm,reth=reth)
			return du,hr

	def DiffCentered(self,u,offsets):
		"""
		First order finite differences, 
		computed using the second order accurate centered scheme.
		Falls back to upwind finite differences close to the boundary.
		"""
		du = fd.DiffCentered(u+self._ExteriorNaNs,offsets,self.gridscale)
		mask = self._BoundaryLayer(u,du)
		du1 = self.DiffUpwind(u,offsets)
		du[mask]=du1[mask]
		#du[mask] = self.DiffUpwind(u[mask],offsets[:,mask],h,grid[:,mask])
		return du



	def Diff2(self,u,offsets):
		"""
		Second order finite differences.
		Second order accurate in the interior, 
		but only first order accurate at the boundary.
		"""
		du0,h0 = self.DiffUpwind(u, offsets,		  reth=True)
		du1,h1 = self.DiffUpwind(u,-np.array(offsets),reth=True)

		return (du0+du1)*(2./(h0+h1))

class MockDirichlet(object):
	"""
	Implements a crude version of Dirichlet boundary conditions, 
	where the boundary conditions are given on the full domain complement.

	(No geometrical computations involved.)
	"""

	def __init__(self,grid_values,gridscale,padding=np.nan):
		if isinstance(grid_values,tuple):
			grid_values = np.full(grid_values,np.nan)
		self.grid_values=grid_values
		self.gridscale=gridscale
		self.padding = padding


	@property
	def interior(self):
		return np.isnan(self.grid_values)

	@property
	def not_interior(self):
		return np.logical_not(self.interior)
	
	@property
	def shape(self): 
		return self.grid_values.shape
	
	def as_field(self,arr,conditional=True):
		return fd.as_field(arr,self.shape,conditional=conditional)

	def DiffUpwind(self,u,offsets): 
		return fd.DiffUpwind(u,offsets,self.gridscale,padding=self.padding)

	def DiffCentered(self,u,offsets): 
		return fd.DiffCentered(u,offsets,self.gridscale,padding=self.padding)

	def Diff2(self,u,offsets,*args): 
		return fd.Diff2(u,offsets,self.gridscale,*args,padding=self.padding)

	
	
		