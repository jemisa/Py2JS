#!/usr/bin/env python

# MIT License
# 
# Copyright (c) 2017 1e618f4
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import ast

# A VERY hacky, quickly-put-together syntax converter for Python to Javascript.
# It performs no semantic analysis.
# Its goal is to reduce mundane typing (e.g. adding semicolons)
# during such a conversion, not to perform an automatic translation.

class JSPrinter(object):
	def __init__(self):
		self.indentation = 0
		self.scope = (-1, ())
		self.needs_indent = True
	def write(self, s):
		if self.needs_indent:
			sys.stdout.write("\t" * self.indentation)
			self.needs_indent = False
		sys.stdout.write(s)
	def write_line(self):
		sys.stdout.write("\n")
		self.needs_indent = True
	def write_line_or_space(self):
		return self.write(" ")
	def get_locals_impl(self, body, stack={}.get(None), result={}.get(None)):
		if stack is None: stack = []
		if result is None: result = {}
		nstack = len(stack)
		for i, node in enumerate(body):
			stack.append(id(node))
			if isinstance(node, ast.FunctionDef) or isinstance(node, ast.Lambda):
				pass
			elif isinstance(node, ast.Assign):  # TODO: 'for' and 'with' also assign to variables...
				for target_or_targets in node.targets:
					for target in [target_or_targets] if isinstance(target_or_targets, ast.Name) else target_or_targets.elts if isinstance(target_or_targets, ast.List) or isinstance(target_or_targets, ast.Tuple) else []:
						if target.id not in result:
							result[target.id] = (len(result), tuple(stack))
						n = 0
						for item in result[target.id][1]:
							if n >= len(stack) or stack[n] != item:
								break
							n += 1
						result[target.id] = (result[target.id][0], result[target.id][1][:n])
			elif isinstance(node, ast.If) or isinstance(node, ast.For) or isinstance(node, ast.While) or isinstance(node, ast.TryExcept) or isinstance(node, ast.TryFinally) or isinstance(node, ast.With):
				for childname in ['body', 'handlers', 'finalbody', 'orelse']:
					child = getattr(node, childname, None)
					if child is not None:
						result = self.get_locals_impl(child, stack, result)
			elif isinstance(node, ast.Global):
				for name in node.names:
					if name not in result:
						result[name] = (len(result), tuple(stack))
					result[name] = (result[name][0], result[name][1][:0])
		del stack[nstack:]
		return result
	def get_locals(self, body):  # TODO: Take into account variable reads, not just writes
		result = {}
		locals_ = self.get_locals_impl(body)
		for key, (i, stack) in sorted(locals_.items(), key=lambda p: p[1][0]):
			if len(stack) > 0:
				node = stack[-1]
				if node not in result: result[node] = []
				result[node].append(key)
		return result
	def __call__(self, node, statements=False):
		write = self.write
		write_line = self.write_line
		write_line_or_space = self.write_line_or_space
		if statements:
			for child in node:
				singular_assignee = child.targets[0].id if isinstance(child, ast.Assign) and len(child.targets) > 0 and isinstance(child.targets[0], ast.Name) else None
				declare_singular_assignee = False
				if id(child) in self.scope:
					n = 0
					for name in self.scope[id(child)]:
						if name == singular_assignee:
							declare_singular_assignee = True
						else:
							if n == 0:
								write("var")
							else:
								write(",")
							write(" ")
							write(name)
							n += 1
					if n:
						write(";")
						write_line()
				if declare_singular_assignee:
					write("var")
					write(" ")
				self(child)
		elif isinstance(node, ast.Module):
			outer_scope = self.scope
			self.scope = self.get_locals(node.body)
			self(node.body, True)
			self.scope = outer_scope
		elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.Lambda):
			is_lambda = isinstance(node, ast.Lambda)
			outer_scope = self.scope
			self.scope = self.get_locals(node.body) if not is_lambda else outer_scope
			write("function")
			write(" ")
			if not is_lambda:
				write(node.name)
			write("(")
			self(node.args)
			write(")")
			if is_lambda:
				write(" ")
			else:
				write_line_or_space()
			write("{")
			if is_lambda:
				write(" ")
				write("return")
				write(" ")
			else:
				write_line()
			self.indentation += 1
			self(node.body, not is_lambda)
			self.indentation -= 1
			if is_lambda:
				write(";")
				write(" ")
			write("}")
			if not is_lambda:
				write_line()
			self.scope = outer_scope
		elif isinstance(node, ast.arguments):
			for i, child in enumerate(node.args):
				if i:
					write(",")
					write(" ")
				self(child)
				if i >= len(node.args) - len(node.defaults):
					write(" ")
					write("/*")
					write("=")
					write(" ")
					self(node.defaults[i - len(node.args)])
					write("*/")
			if node.vararg or node.kwarg:
				if len(node.args) > 0:
					write(",")
					write(" ")
				write(node.vararg or node.kwarg)
				write("...")
		elif isinstance(node, ast.Name):
			name = node.id
			if name == repr(None):
				name = "null"
			write(name)
		elif isinstance(node, ast.IfExp):
			write("(")
			write("(")
			self(node.test)
			write(")")
			write(" ")
			write("?")
			write(" ")
			self(node.body)
			write(" ")
			write(":")
			write(" ")
			write("(")
			self(node.orelse)
			write(")")
			write(")")
		elif isinstance(node, ast.While):
			write("while")
			write(" ")
			write("(")
			self(node.test)
			write(")")
			if not isinstance(node.test, ast.BinOp):
				write(" /* WARNING: Empty containers are NOT false in Javascript! */")
			write_line_or_space()
			write("{")
			write_line()
			self.indentation += 1
			self(node.body, True)
			self.indentation -= 1
			write("}")
			write_line()
			if node.orelse:
				raise ValueError("orelse not supported")
		elif isinstance(node, ast.For):
			first_statement = None
			if (
				isinstance(node.target, ast.Name) and isinstance(node.iter, ast.Name) or
				isinstance(node.target, ast.Tuple) and len(node.target.elts) == 2 and isinstance(node.target.elts[0], ast.Name) and isinstance(node.iter, ast.Call) and len(node.iter.args) == 1 and isinstance(node.iter.args[0], ast.Name) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == enumerate.__name__
			):
				if isinstance(node.iter, ast.Name):
					index = ast.Name(node.target.id + "$index", node.target.ctx)
				else:
					index = node.target.elts[0]
				write("for")
				write(" ")
				write("(")
				write("var")
				write(" ")
				self(index)
				write(" ")
				write("=")
				write(" ")
				self(ast.Num(0))
				write(";")
				write(" ")
				self(index)
				write(" ")
				write("<")
				write(" ")
				container = node.iter if isinstance(node.iter, ast.Name) else node.iter.args[0]
				self(ast.Call(ast.Name(len.__name__, None), [container], [], [], []))
				write(";")
				write(" ")
				write("++")
				self(index)
				write(")")
				first_statement = ast.Assign([node.target if isinstance(node.iter, ast.Name) else node.target.elts[1]], ast.Subscript(container, ast.Index(index), None))
			else:
				write("for")
				write(" ")
				write("(")
				write("var")
				write(" ")
				self(node.target)
				write(" ")
				write("in")
				write(" ")
				self(node.iter)
				write(")")
			write_line_or_space()
			write("{")
			write_line()
			self.indentation += 1
			if first_statement is not None:
				self(first_statement)
			self(node.body, True)
			self.indentation -= 1
			write("}")
			write_line()
			if node.orelse:
				raise ValueError("orelse not supported")
		elif isinstance(node, ast.If):
			while 1:
				write("if")
				write(" ")
				write("(")
				self(node.test)
				write(")")
				write_line_or_space()
				write("{")
				self.indentation += 1
				write_line()
				self(node.body, True)
				self.indentation -= 1
				write("}")
				if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
					write_line_or_space()
					write("else")
					write(" ")
					[node] = node.orelse
				elif node.orelse:
					write_line_or_space()
					write("else")
					write_line_or_space()
					write("{")
					self.indentation += 1
					write_line()
					for statement in node.orelse:
						self(statement)
					self.indentation -= 1
					write("}")
					write_line()
					break
				else:
					write_line()
					break
		elif isinstance(node, ast.Pass): pass
		elif isinstance(node, ast.Index):
			write("[")
			self(node.value)
			write("]")
		elif isinstance(node, ast.Slice):
			write(".")
			write("slice")
			write("(")
			if node.lower is not None:
				self(node.lower)
			else:
				self(ast.Num(0))
			if node.upper is not None or node.step is not None:
				write(",")
				write(" ")
			if node.upper is not None:
				self(node.upper)
			if node.step is not None:
				write(",")
				write(" ")
				self(node.step)
			write(")")
		elif isinstance(node, ast.Subscript):
			self(node.value)
			self(node.slice)
		elif isinstance(node, ast.Break):
			write("break")
			write(";")
			write_line()
		elif isinstance(node, ast.Continue):
			write("continue")
			write(";")
			write_line()
		elif isinstance(node, ast.Yield):
			write("yield")
			write("(")
			self(node.value)
			write(")")
			write(" /* WARNING: Yield not supported */")
		elif isinstance(node, ast.Compare):
			self(node.left)
			for i, (op, c) in enumerate(zip(node.ops, node.comparators)):
				if i > 0:
					write(" ")
					write("&&")
					write(" ")
					self(node.comparators[i - 1])
					if not isinstance(node.comparators[i - 1], ast.Name):
						write(" /* WARNING: expression re-evaluated! */")
				write(" ")
				self(op)
				write(" ")
				self(c)
		elif isinstance(node, ast.Return):
			write("return")
			write(" ")
			self(node.value)
			write(";")
			write_line()
		elif isinstance(node, ast.AugAssign):
			self(node.target)
			write(" ")
			self(node.op)
			write("=")
			write(" ")
			self(node.value)
			write(";")
			write_line()
		elif isinstance(node, ast.Assign):
			for i, target in enumerate(node.targets):
				self(target)
				write(" ")
				write("=")
				write(" ")
			self(node.value)
			write(";")
			write_line()
		elif isinstance(node, ast.Delete):
			n = 0
			for target in node.targets:
				if isinstance(target, ast.Subscript):
					self(target.value)
					write(".")
					write("splice")
					write("(")
					if target.slice.lower is not None:
						self(target.slice.lower)
					else:
						self(ast.Num(0))
					write(",")
					write(" ")
					if target.slice.upper is not None:
						self(target.slice.upper)
					else:
						self(ast.Call(ast.Name(len.__name__, None), [target.value], [], [], []))
					if target.slice.step is not None and target.slice.step != 1:
						raise ValueError("cannot delete slice with step")
					write(")")
					write(";")
					write_line()
					n += 1
			if n < len(node.targets):
				write("delete")
				write(" ")
				n = 0
				for target in node.targets:
					if not isinstance(target, ast.Subscript):
						if n > 0:
							write(",")
							write(" ")
						self(target)
						n += 1
				write(";")
				write_line()
		elif isinstance(node, ast.Num):
			write(str(node.n))
		elif isinstance(node, ast.List):
			write("[")
			for i, key in enumerate(node.elts):
				if i > 0:
					write(",")
					write(" ")
				self(node.elts[i])
			write("]")
		elif isinstance(node, ast.Expr):
			self(node.value)
			write(";")
			write_line()
		elif isinstance(node, ast.Tuple):
			write("[")
			for i, key in enumerate(node.elts):
				if i > 0:
					write(",")
					write(" ")
				self(node.elts[i])
			if False and len(node.elts) == 1:
				write(",")
			write("]")
		elif isinstance(node, ast.Dict):
			write("{")
			for i, key in enumerate(node.keys):
				if i > 0:
					write(",")
					write(" ")
				self(node.keys[i])
				write(":")
				write(" ")
				self(node.values[i])
			write("}")
		elif isinstance(node, ast.Raise):
			write("throw")
		elif isinstance(node, ast.Global):
			pass
		elif isinstance(node, ast.Attribute):
			self(node.value)
			write(".")
			write(node.attr)
		elif isinstance(node, ast.Call):
			if isinstance(node.func, ast.Name) and node.func.id == len.__name__ and len(node.args) == 1:
				self(ast.Attribute(node.args[0], "length", node.func.ctx))
			elif isinstance(node.func, ast.Attribute) and node.func.attr == list.extend.__name__:
				self(ast.Call(ast.Attribute(ast.Attribute(ast.Attribute(ast.Name("Array", node.func.ctx), "prototype", node.func.ctx), "push", node.func.ctx), "apply", node.func.ctx), [node.func.value] + node.args, [], [], []))
			else:
				self(node.func)
				write("(")
				for i, arg in enumerate(node.args):
					if i > 0:
						write(",")
						write(" ")
					self(arg)
				write(")")
		elif isinstance(node, ast.UAdd  ): write("+")
		elif isinstance(node, ast.USub  ): write("-")
		elif isinstance(node, ast.Not   ): write("!")
		elif isinstance(node, ast.Or    ): write("||")
		elif isinstance(node, ast.And   ): write("&&")
		elif isinstance(node, ast.BitAnd): write("&")
		elif isinstance(node, ast.BitOr ): write("|")
		elif isinstance(node, ast.BitXor): write("^")
		elif isinstance(node, ast.Add   ): write("+")
		elif isinstance(node, ast.Sub   ): write("-")
		elif isinstance(node, ast.Mult  ): write("*")
		elif isinstance(node, ast.Div   ): write("/")
		elif isinstance(node, ast.Lt    ): write("<")
		elif isinstance(node, ast.LtE   ): write("<=")
		elif isinstance(node, ast.Gt    ): write(">")
		elif isinstance(node, ast.GtE   ): write(">=")
		elif isinstance(node, ast.Eq    ): write("==")
		elif isinstance(node, ast.NotEq ): write("!=")
		elif isinstance(node, ast.In    ): write("in")
		elif isinstance(node, ast.Is    ): write("is")
		elif isinstance(node, ast.IsNot ): write("!is")
		elif isinstance(node, ast.Str   ): write("\"" + node.s.encode('string_escape') + "\"")
		elif isinstance(node, ast.BoolOp):
			for i, value in enumerate(node.values):
				if i > 0:
					write(" ")
					self(node.op)
					write(" ")
				self(value)
		elif isinstance(node, ast.UnaryOp):
			self(node.op)
			self(node.operand)
		elif isinstance(node, ast.BinOp):
			self(node.left)
			write(" ")
			self(node.op)
			write(" ")
			self(node.right)
		elif isinstance(node, ast.Import):
			write("var")
			for i, name in enumerate(node.names):
				if i > 0:
					write(",")
				write(" ")
				write(name.asname or name.name)
				write(" ")
				write("=")
				write(" ")
				write("import")
				write("(")
				write("\"")
				write(name.name)
				write("\"")
				write(")")
			write(";")
			write_line()
		else:
			raise NotImplementedError("Unsupported: " + node.__class__.__name__)


def main(program):
	JSPrinter()(ast.parse(sys.stdin.read()))

if __name__ == '__main__':
	import sys
	raise SystemExit(main(*sys.argv))
