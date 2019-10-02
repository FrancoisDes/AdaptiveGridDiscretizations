from NumericalSchemes import FiniteDifferences as fd
from NumericalSchemes import AutomaticDifferentiation as ad
from NumericalSchemes import LinearParallel as lp

import numpy as np
from functools import reduce
from itertools import cycle

class Domain(object):
	"""
	This class represents a domain from which one can query 
	a level set function, the boundary distance in a given direction,
	 and some related methods.

	The base class represents the full space R^d.
	"""

	def level(self,x):
		"""
		A level set function, negative inside, positive outside.
		Different, but equivalent up to a multiplicative constant, 
		to the signed distance from the boundary.
		"""
		return -np.inf

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
		shape = (1,)+x.shape[1:]
		return np.full(shape,-np.inf),np.full(shape,np.inf)


	def freeway(self,x,v):
		"""
		Output : Least h>=0 such that x+h*v intersects the boundary.
		"""
		a,b = self.intervals(x,v)
		a[a<0]=np.inf
		b[b<0]=np.inf
		return np.minimum(a.min(axis=0),b.min(axis=0))

class Ball(Domain):
	"""
	This class represents a ball shaped domain
	"""

	def __init__(self,center,radius=1.):
		if not isinstance(center,np.ndarray): center=np.array(center)
		self.center=center
		self.radius=radius

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

	def __init__(self,sides):
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
		hlen,xc,vc = (e[pos] for e in (hlen,xc,vc))

		a[pos] = (-hlen-xc)/vc
		b[pos] = ( hlen-xc)/vc

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
	def __init__(self,doms):
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
	return Intersection((dom1,AbsoluteComplement(dom2)))

def Union(doms):
	"""
	Union of various domains.
	"""
	return AbsoluteComplement(Intersection([AbsoluteComplement(dom) for dom in doms]))

class Dirichlet(object):
	"""
	Implements Dirichlet boundary conditions.
	Replaces all NaN values with values obtained on the boundary along the given direction
	"""

	def __init__(self,dom,bc,grid=None):
		"""
		Domain, boundary conditions, default grid.
		"""
		self.dom = dom
		self.bc = bc
		self.grid = grid

	def _grid(self,u,grid=None):
		if grid is None: grid=self.grid
		dim = len(grid)
		assert dim==0 or u.shape[-dim:]==grid.shape[1:]
		return grid

	@staticmethod
	def _BoundaryLayer(u,du):
		"""
		Returns positions at which u is defined but du is not.
		"""
		return np.logical_and(np.isnan(du),np.logical_not(np.isnan(u)))

	def _DiffUpwindDirichlet(self,u,offsets,grid,reth):
		"""
		Returns first order finite differences w.r.t. boundary value.
		"""
		h = self.dom.freeway(grid,offsets)
		x = grid+h*offsets
		bc = self.bc(x)
		result = (bc-u)/h
		return (result,h) if reth else result


	def DiffUpwind(self,u,offsets,h,grid=None,reth=False):
		"""
		Returns first order finite differences, uses boundary values when needed.
		"""
		grid=self._grid(u,grid)
		du = fd.DiffUpwind(u,offsets,h)
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
			hr = np.full(offsets.shape[1:],h)
			du[mask],hr[mask] = self._DiffUpwindDirichlet(um,om,gm,reth=reth)
			return du,hr

	def DiffCentered(self,u,offsets,h,grid=None):
		"""
		Falls back to upwind finite differences at the boundary.
		"""
		grid=self._grid(u,grid)
		du = fd.DiffCentered(u,offsets,h)
		mask = self._BoundaryLayer(u,du)
		du1 = self.DiffUpwind(u,offsets,h,grid)
		du[mask]=du1[mask]
		#du[mask] = self.DiffUpwind(u[mask],offsets[:,mask],h,grid[:,mask])
		return du



	def Diff2(self,u,offsets,h,grid=None):
		"""
		Only first order accurate at the boundary.
		"""
		grid=self._grid(u,grid)
		d2u = fd.Diff2(u,offsets,h)
		mask = self._BoundaryLayer(u,d2u)

#		um,om,gm = u[mask], offsets[:,mask], grid[:,mask]
#		du0,h0 = self.DiffUpwind(um, om,h,gm, reth=True)
#		du1,h1 = self.DiffUpwind(um,-om,h,gm, reth=True)

		du0,h0 = self.DiffUpwind(u, offsets,h,grid, reth=True)
		du1,h1 = self.DiffUpwind(u,-np.array(offsets),h,grid, reth=True)

		du0,h0,du1,h1 = (e[mask] for e in (du0,h0,du1,h1))
		d2u[mask] = (du0+du1)*(2./(h0+h1))
		return d2u



		



#class Polygon2(Domain):
	"""
	Two dimensional polygon
	"""
"""
	def __init__(self,pts,convex=None):
		self.pts = pts
		if convex is None:
			assert False
		self.convex=convex

		assert False
		self.normals=None
		self.shifts=None

	def level(self,x):
		normals,shifts = (fd.as_field(e,x.shape[1:],conditional=False) 
			for e in (self.normals,self.shifts))

		return np.maximum(lp.dot_VA(x,normals)+shifts)

	def distance(self,x):
"""

