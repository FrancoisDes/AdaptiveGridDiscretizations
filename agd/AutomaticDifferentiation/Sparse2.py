import numpy as np
from . import misc
from . import Sparse
from . import Dense2

_add_dim = misc._add_dim; _pad_last = misc._pad_last; _concatenate=misc._concatenate;


class spAD2(np.ndarray):
	"""
	A class for sparse forward second order automatic differentiation
	"""

	# Construction
	# See : https://docs.scipy.org/doc/numpy-1.13.0/user/basics.subclassing.html
	def __new__(cls,value,coef1=None,index=None,coef2=None,index_row=None,index_col=None,broadcast_ad=False):
		if isinstance(value,spAD2):
			assert coef1 is None and index is None and coef2 is None and index_row is None and index_col is None
			return value
		obj = np.asarray(value).view(spAD2)
		shape = obj.shape
		shape2 = shape+(0,)
		assert ((coef1 is None) and (index is None)) or (coef1.shape==index.shape)
		obj.coef1 = (np.full(shape2,0.) if coef1  is None 
			else misc._test_or_broadcast_ad(coef1,shape,broadcast_ad) )
		obj.index = (np.full(shape2,0)  if index is None  
			else misc._test_or_broadcast_ad(index,shape,broadcast_ad) )
		
		assert (((coef2 is None) and (index_row is None) and (index_col is None)) 
			or ((coef2.shape==index_row.shape) and (coef2.shape==index_col.shape)))
		obj.coef2 = (np.full(shape2,0.) if coef2  is None 
			else misc._test_or_broadcast_ad(coef2,shape,broadcast_ad) )
		obj.index_row = (np.full(shape2,0)  if index_row is None 
			else misc._test_or_broadcast_ad(index_row,shape,broadcast_ad) )
		obj.index_col = (np.full(shape2,0)  if index_col is None 
			else misc._test_or_broadcast_ad(index_col,shape,broadcast_ad) )
		return obj

#	def __array_finalize__(self,obj): pass

	def copy(self,order='C'):
		return spAD2(self.value.copy(order=order),
			self.coef1.copy(order=order),self.index.copy(order=order),
			self.coef2.copy(order=order),self.index_row.copy(order=order),self.index_col.copy(order=order))

	# Representation 
	def __iter__(self):
		for value,coef1,index,coef2,index_row,index_col in zip(self.value,self.coef1,self.index,self.coef2,self.index_row,self.index_col):
			yield spAD2(value,coef1,index,coef2,index_row,index_col)

	def __str__(self):
		return "spAD2"+str((self.value,self.coef1,self.index,self.coef2,self.index_row,self.index_col))
	def __repr__(self):
		return "spAD2"+repr((self.value,self.coef1,self.index,self.coef2,self.index_row,self.index_col))	

	# Operators
	def __add__(self,other):
		if isinstance(other,spAD2):
			value = self.value+other.value; shape = value.shape
			return spAD2(value, 
				_concatenate(self.coef1,other.coef1,shape), _concatenate(self.index,other.index,shape),
				_concatenate(self.coef2,other.coef2,shape), _concatenate(self.index_row,other.index_row,shape), _concatenate(self.index_col,other.index_col,shape))
		else:
			return spAD2(self.value+other, self.coef1, self.index, self.coef2, self.index_row, self.index_col, broadcast_ad=True)

	def __sub__(self,other):
		if isinstance(other,spAD2):
			value = self.value-other.value; shape = value.shape
			return spAD2(value, 
				_concatenate(self.coef1,-other.coef1,shape), _concatenate(self.index,other.index,shape),
				_concatenate(self.coef2,-other.coef2,shape), _concatenate(self.index_row,other.index_row,shape), _concatenate(self.index_col,other.index_col,shape))
		else:
			return spAD2(self.value-other, self.coef1, self.index, self.coef2, self.index_row, self.index_col, broadcast_ad=True)

	def __mul__(self,other):
		if isinstance(other,spAD2):
			value = self.value*other.value
			coef1_a,coef1_b = _add_dim(other.value)*self.coef1,_add_dim(self.value)*other.coef1
			index_a,index_b = np.broadcast_to(self.index,coef1_a.shape),np.broadcast_to(other.index,coef1_b.shape)
			coef2_a,coef2_b = _add_dim(other.value)*self.coef2,_add_dim(self.value)*other.coef2
			index_row_a,index_row_b = np.broadcast_to(self.index_row,coef2_a.shape),np.broadcast_to(other.index_row,coef2_b.shape)
			index_col_a,index_col_b = np.broadcast_to(self.index_col,coef2_a.shape),np.broadcast_to(other.index_col,coef2_b.shape)

			len_a,len_b = self.coef1.shape[-1],other.coef1.shape[-1]
			coef2_ab = np.repeat(self.coef1,len_b,axis=-1) * np.tile(other.coef1,len_a) 
			index2_a = np.broadcast_to(np.repeat(self.index,len_b,axis=-1),coef2_ab.shape)
			index2_b = np.broadcast_to(np.tile(other.index,len_a),coef2_ab.shape)

			return spAD2(value,_concatenate(coef1_a,coef1_b),_concatenate(index_a,index_b),
				np.concatenate((coef2_a,coef2_b,coef2_ab,coef2_ab),axis=-1),
				np.concatenate((index_row_a,index_row_b,index2_a,index2_b),axis=-1),
				np.concatenate((index_col_a,index_col_b,index2_b,index2_a),axis=-1))
		elif isinstance(other,np.ndarray):
			value = self.value*other
			coef1 = _add_dim(other)*self.coef1
			index = np.broadcast_to(self.index,coef1.shape)
			coef2 = _add_dim(other)*self.coef2
			index_row = np.broadcast_to(self.index_row,coef2.shape)
			index_col = np.broadcast_to(self.index_col,coef2.shape)
			return spAD2(value,coef1,index,coef2,index_row,index_col)
		else:
			return spAD2(self.value*other,other*self.coef1,self.index,other*self.coef2,self.index_row,self.index_col)

	def __truediv__(self,other):
		if isinstance(other,spAD2):
			return self.__mul__(other.__pow__(-1))
		elif isinstance(other,np.ndarray):
			inv = 1./other
			return spAD2(self.value*inv,self.coef1*_add_dim(inv),self.index,
				self.coef2*_add_dim(inv),self.index_row,self.index_col)
		else:
			inv = 1./other
			return spAD2(self.value*inv,self.coef1*inv,self.index,self.coef2*inv,self.index_row,self.index_col)

	__rmul__ = __mul__
	__radd__ = __add__
	def __rsub__(self,other): 		return -(self-other)
	def __rtruediv__(self,other):
		return self.__pow__(-1).__mul__(other)

	def __neg__(self):		return spAD2(-self.value,-self.coef1,self.index,-self.coef2,self.index_row,self.index_col)

	# Math functions
	def _math_helper(self,deriv): # Inputs : a=f(x), b=f'(x), c=f''(x), where x=self.value
		a,b,c=deriv
		len_1 = self.coef1.shape[-1]
		coef1_r,index_r = np.repeat(self.coef1,len_1,axis=-1),np.repeat(self.index,len_1,axis=-1)
		coef1_t,index_t = np.tile(self.coef1,len_1),np.tile(self.index,len_1) 
		return spAD2(a,_add_dim(b)*self.coef1,self.index,
			_concatenate(_add_dim(b)*self.coef2,_add_dim(c)*(coef1_r*coef1_t)),
			_concatenate(self.index_row, index_r),_concatenate(self.index_col, index_t))
	
	def sqrt(self):			return self**0.5
	def __pow__(self,n):	return self._math_helper(misc.pow2(self.value,n))
	def log(self):			return self._math_helper(misc.log2(self.value))
	def exp(self):			return self._math_helper(misc.exp2(self.value))
	def abs(self):			return self._math_helper(misc.abs2(self.value))
	def sin(self):			return self._math_helper(misc.sin2(self.value))
	def cos(self):			return self._math_helper(misc.cos2(self.value))
	def tan(self):			return self._math_helper(misc.tan2(self.value))
	def arcsin(self):		return self._math_helper(misc.arcsin2(self.value))
	def arccos(self):		return self._math_helper(misc.arccos2(self.value))
	def arctan(self):		return self._math_helper(misc._arctan2(self.value))
	def sinh(self):			return self._math_helper(misc.sinh2(self.value))
	def cosh(self):			return self._math_helper(misc.cosh2(self.value))
	def tanh(self):			return self._math_helper(misc.tanh2(self.value))
	def arcsinh(self):		return self._math_helper(misc.arcsinh2(self.value))
	def arccosh(self):		return self._math_helper(misc.arccosh2(self.value))
	def arctanh(self):		return self._math_helper(misc._arctanh2(self.value))

	@staticmethod
	def compose(a,t):
		assert isinstance(a,Dense2.denseAD2) and all(isinstance(b,spAD2) for b in t)
		b = np.moveaxis(spAD2.concatenate(t,axis=0),0,-1) # Possible performance hit if ad sizes are inhomogeneous
		coef1 = _add_dim(a.coef1)*b.coef1
		index1 = np.broadcast_to(b.index,coef1.shape)
		coef2_pure = _add_dim(a.coef1)*b.coef2
		index_row_pure = np.broadcast_to(b.index_row,coef2_pure.shape)
		index_col_pure = np.broadcast_to(b.index_col,coef2_pure.shape)

		s = b.shape[:-1]; na = a.size_ad; nb = b.size_ad1;
		coef2_mixed = misc._add_dim2(a.coef2)*np.reshape(b.coef1,s+(na,1,nb,1))*np.reshape(b.coef1,s+(1,na,1,nb))
		s2 = coef2_mixed.shape
		index_row_mixed = np.broadcast_to(b.index.reshape(s+(na,1,nb,1)),s2)
		index_col_mixed = np.broadcast_to(b.index.reshape(s+(1,na,1,nb)),s2)
		#s3 = s2[:-4]+(na*na*nb*nb,) a.reshape(s3)

		coef1,index1,coef2_pure,index_row_pure,index_col_pure = (_flatten_nlast(a,2) for a in (coef1,index1,coef2_pure,index_row_pure,index_col_pure))
		coef2_mixed,index_row_mixed,index_col_mixed = (_flatten_nlast(a,4) for a in (coef2_mixed,index_row_mixed,index_col_mixed))
		
		return spAD2(a.value,coef1,index1,
			_concatenate(coef2_pure,coef2_mixed),_concatenate(index_row_pure,index_row_mixed),_concatenate(index_col_pure,index_col_mixed))

	#Indexing
	@property
	def value(self): return self.view(np.ndarray)
	@property
	def size_ad1(self):  return self.coef1.shape[-1]
	@property
	def size_ad2(self):  return self.coef2.shape[-1]

	def __getitem__(self,key):
		ekey = misc.key_expand(key)
		return spAD2(self.value[key], 
			self.coef1[ekey], self.index[ekey], 
			self.coef2[ekey], self.index_row[ekey], self.index_col[ekey])

	def __setitem__(self,key,other):
		ekey = misc.key_expand(key)
		if isinstance(other,spAD2):
			self.value[key] = other.value

			pad_size = max(self.coef1.shape[-1],other.coef1.shape[-1])
			if pad_size>self.coef1.shape[-1]:
				self.coef1 = _pad_last(self.coef1,pad_size)
				self.index = _pad_last(self.index,pad_size)
			self.coef1[ekey] = _pad_last(other.coef1,pad_size)
			self.index[ekey] = _pad_last(other.index,pad_size)

			pad_size = max(self.coef2.shape[-1],other.coef2.shape[-1])
			if pad_size>self.coef2.shape[-1]:
				self.coef2 = _pad_last(self.coef2,pad_size)
				self.index_row = _pad_last(self.index_row,pad_size)
				self.index_col = _pad_last(self.index_col,pad_size)
			self.coef2[ekey] = _pad_last(other.coef2,pad_size)
			self.index_row[ekey] = _pad_last(other.index_row,pad_size)
			self.index_col[ekey] = _pad_last(other.index_col,pad_size)
		else:
			self.value[key] = other
			self.coef1[ekey] = 0.
			self.coef2[ekey] = 0.

	def reshape(self,shape,order='C'):
		shape1 = (shape if isinstance(shape,tuple) else (shape,))+(self.size_ad1,)
		shape2 = (shape if isinstance(shape,tuple) else (shape,))+(self.size_ad2,)
		return spAD2(self.value.reshape(shape,order=order),self.coef1.reshape(shape1,order=order), self.index.reshape(shape1,order=order),
			self.coef2.reshape(shape2,order=order),self.index_row.reshape(shape2,order=order),self.index_col.reshape(shape2,order=order))

	def flatten(self):	return self.reshape( (self.size,) )
	def squeeze(self,axis=None): return self.reshape(self.value.squeeze(axis).shape)

	def broadcast_to(self,shape):
		shape1 = shape+(self.size_ad1,)
		shape2 = shape+(self.size_ad2,)
		return spAD2(np.broadcast_to(self.value,shape), np.broadcast_to(self.coef1,shape1), np.broadcast_to(self.index,shape1),
			np.broadcast_to(self.coef2,shape2), np.broadcast_to(self.index_row,shape2), np.broadcast_to(self.index_col,shape2))

	@property
	def T(self):	return self if self.ndim<2 else self.transpose()
	
	def transpose(self,axes=None):
		if axes is None: axes = tuple(reversed(range(self.ndim)))
		axes2 = tuple(axes) +(self.ndim,)
		return spAD2(self.value.transpose(axes),self.coef1.transpose(axes2),self.index.transpose(axes2),
			self.coef2.transpose(axes2),self.index_row.transpose(axes2),self.index_col.transpose(axes2))

	# Reductions
	def sum(self,axis=None,out=None,**kwargs):
		if axis is None: return self.flatten().sum(axis=0,out=out,**kwargs)
		value = self.value.sum(axis,**kwargs)

		shape1 = value.shape + (self.size_ad1 * self.shape[axis],)
		coef1 = np.moveaxis(self.coef1, axis,-1).reshape(shape1)
		index = np.moveaxis(self.index, axis,-1).reshape(shape1)

		shape2 = value.shape + (self.size_ad2 * self.shape[axis],)
		coef2 = np.moveaxis(self.coef2, axis,-1).reshape(shape2)
		index_row = np.moveaxis(self.index_row, axis,-1).reshape(shape2)
		index_col = np.moveaxis(self.index_col, axis,-1).reshape(shape2)

		out = spAD2(value,coef1,index,coef2,index_row,index_col)
		return out

	prod = misc.prod

	def min(self,*args,**kwargs): return misc.min(self,*args,**kwargs)
	def max(self,*args,**kwargs): return misc.max(self,*args,**kwargs)
	def argmin(self,*args,**kwargs): return self.value.argmin(*args,**kwargs)
	def argmax(self,*args,**kwargs): return self.value.argmax(*args,**kwargs)

	def sort(self,*varargs,**kwargs):
		from . import sort
		self=sort(self,*varargs,**kwargs)


	# See https://docs.scipy.org/doc/numpy/reference/ufuncs.html
	def __array_ufunc__(self,ufunc,method,*inputs,**kwargs):
#		if ufunc!=np.maximum:
#			print(self)
#			return NotImplemented
		# Return an np.ndarray for piecewise constant functions
		if ufunc in [
		# Comparison functions
		np.greater,np.greater_equal,
		np.less,np.less_equal,
		np.equal,np.not_equal,

		# Math
		np.floor_divide,np.rint,np.sign,np.heaviside,

		# Floating functions
		np.isfinite,np.isinf,np.isnan,np.isnat,
		np.signbit,np.floor,np.ceil,np.trunc
		]:
			inputs_ = (a.value if isinstance(a,spAD2) else a for a in inputs)
			return super(spAD2,self).__array_ufunc__(ufunc,method,*inputs_,**kwargs)


		if method=="__call__":

			# Reimplemented
			if ufunc==np.maximum: return misc.maximum(*inputs,**kwargs)
			if ufunc==np.minimum: return misc.minimum(*inputs,**kwargs)

			# Math functions
			if ufunc==np.sqrt:		return self.sqrt()
			if ufunc==np.log:		return self.log()
			if ufunc==np.exp:		return self.exp()
			if ufunc==np.abs:		return self.abs()
			if ufunc==np.sin:		return self.sin()
			if ufunc==np.cos:		return self.cos()
			if ufunc==np.tan:		return self.tan()
			if ufunc==np.arcsin:	return self.arcsin()
			if ufunc==np.arccos:	return self.arccos()
			if ufunc==np.arctan:	return self.arctan()
			if ufunc==np.sinh:		return self.sinh()
			if ufunc==np.cosh:		return self.cosh()
			if ufunc==np.tanh:		return self.tanh()
			if ufunc==np.arcsinh:	return self.arcsinh()
			if ufunc==np.arccosh:	return self.arccosh()
			if ufunc==np.arctanh:	return self.arctanh()

			# Operators
			if ufunc==np.add: return self.add(*inputs,**kwargs)
			if ufunc==np.subtract: return self.subtract(*inputs,**kwargs)
			if ufunc==np.multiply: return self.multiply(*inputs,**kwargs)
			if ufunc==np.true_divide: return self.true_divide(*inputs,**kwargs)


		return NotImplemented

	# Conversion
	def bound_ad(self):
		return 1+np.max((np.max(self.index,initial=-1),np.max(self.index_row,initial=-1),np.max(self.index_col,initial=-1)))
	def to_dense(self,dense_size_ad=None):
		def mvax(arr): return np.moveaxis(arr,-1,0)
		dsad = self.bound_ad() if dense_size_ad is None else dense_size_ad
		coef1 = np.zeros(self.shape+(dsad,))
		for c,i in zip(mvax(self.coef1),mvax(self.index)):
			np.put_along_axis(coef1,_add_dim(i),np.take_along_axis(coef1,_add_dim(i),axis=-1)+_add_dim(c),axis=-1)
		coef2 = np.zeros(self.shape+(dsad*dsad,))
		for c,i in zip(mvax(self.coef2),mvax(self.index_row*dsad+self.index_col)):
			np.put_along_axis(coef2,_add_dim(i),np.take_along_axis(coef2,_add_dim(i),axis=-1)+_add_dim(c),axis=-1)
		return Dense2.denseAD2(self.value,coef1,np.reshape(coef2,self.shape+(dsad,dsad)))
	def to_first(self):
		return Sparse.spAD(self.value,self.coef1,self.index)

	#Linear algebra
	def triplets(self):
		return (self.coef2,(self.index_row,self.index_col))

	def solve_stationnary(self,raw=False):
		"""
		Finds a stationnary point to a quadratic function, provided as a spAD2 array scalar. 
		Use "raw = True" to obtain the raw linear system and use your own solver.
		"""
		mat = self.triplets()
		rhs = - self.to_first().to_dense(self.bound_ad()).coef
		return (mat,rhs) if raw else misc.spsolve(mat,rhs)

	def solve_weakform(self,raw=False):
		"""
		Assume that a spAD2 array scalar represents the quadratic function
		Q(u,v) = a0 + a1.(u,v) + (u,v).a2.(u,v) of the variable (u,v).
		Finds u such that Q(u,v) is independent of v.
		Use "raw = True" to obtain the raw linear system and use your own solver.
		"""
		(coef,(row,col)),rhs = self.solve_stationnary(raw=True)
		n = rhs.size//2
		rhs = rhs[n:]
		pos = np.logical_and(row>=n,col<n)
		mat = (coef[pos],(row[pos]-n,col[pos]))
		return (mat,rhs) if raw else misc.spsolve(mat,rhs)
	
	# Static methods

	# Support for +=, -=, *=, /=
	@staticmethod
	def add(*args,**kwargs): return misc.add(*args,**kwargs)
	@staticmethod
	def subtract(*args,**kwargs): return misc.subtract(*args,**kwargs)
	@staticmethod
	def multiply(*args,**kwargs): return misc.multiply(*args,**kwargs)
	@staticmethod
	def true_divide(*args,**kwargs): return misc.true_divide(*args,**kwargs)

	@staticmethod
	def stack(elems,axis=0):
		return spAD2.concatenate(tuple(np.expand_dims(e,axis=axis) for e in elems),axis)

	@staticmethod
	def concatenate(elems,axis=0):
		axis1 = axis if axis>=0 else axis-1
		elems2 = tuple(spAD2(e) for e in elems)
		size_ad1 = max(e.size_ad1 for e in elems2)
		size_ad2 = max(e.size_ad2 for e in elems2)
		return spAD2( 
		np.concatenate(tuple(e.value for e in elems2), axis=axis), 
		np.concatenate(tuple(_pad_last(e.coef1,size_ad1)  for e in elems2),axis=axis1),
		np.concatenate(tuple(_pad_last(e.index,size_ad1)  for e in elems2),axis=axis1),
		np.concatenate(tuple(_pad_last(e.coef2,size_ad2)  for e in elems2),axis=axis1),
		np.concatenate(tuple(_pad_last(e.index_row,size_ad2)  for e in elems2),axis=axis1),
		np.concatenate(tuple(_pad_last(e.index_col,size_ad2)  for e in elems2),axis=axis1))

	def simplify_ad(self):
		spHelper1 = Sparse.spAD(self.value,self.coef1,self.index)
		spHelper1.simplify_ad()
		self.coef1,self.index = spHelper1.coef,spHelper1.index

		n_col = 1+np.max(self.index_col)
		spHelper2 = Sparse.spAD(self.value,self.coef2,self.index_row*n_col + self.index_col)
		spHelper2.simplify_ad()
		self.coef2,self.index_row,self.index_col = spHelper2.coef, spHelper2.index//n_col, spHelper2.index%n_col

# -------- End of class spAD2 -------

# -------- Utilities ------

def _flatten_nlast(a,n):
	assert n>0
	s=a.shape
	return a.reshape(s[:-n]+(np.prod(s[-n:]),))

# -------- Factory method -----

def identity(*args,**kwargs):
	arr = Sparse.identity(*args,**kwargs)
	shape2 = arr.shape+(0,)
	return spAD2(arr.value,arr.coef,arr.index,np.full(shape2,0.),np.full(shape2,0),np.full(shape2,0))

def register(*args,**kwargs):
	return Sparse.register(*args,**kwargs,ident=identity)

