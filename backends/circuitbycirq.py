import os
from collections import defaultdict, Callable
import numpy as np
import sympy
import matplotlib.pyplot as plt
import multiprocessing as mp
from multiprocessing import Pool
import networkx as nx
import cirq

class CircuitByCirq:
    """generate a instance of CircuitByCirq"""

    def __init__(self,
                 # p: int = 1,
                 nodes_weight: list = None,
                 edges_weight: list = None,
                 is_parallel: bool = None) -> None:
        """initialize a instance of CircuitByCirq"""

        self._p = None
        self._nodes_weight = nodes_weight
        self._edges_weight = edges_weight
        self._is_parallel = False if is_parallel is None else is_parallel

        self._element_to_graph = None
        self._pargs = None
        self._expectation_path = []

    def get_operator(self, element, qubit_num):
        qubits = cirq.LineQubit.range(qubit_num)
        nodes = [element] if isinstance(element, int) else list(element)
        op = 1
        for i in range(qubit_num):
            if i in nodes:
                op *= cirq.Z(qubits[i])
        return op

    def get_expectation(self, element_graph):
        """
        transform the graph to circuit according to the computing_framework
        Args:
            graph (nx.Graph): graph to be transformed to circuit
            params (np.array): Optimal parameters
            original_e (Optional[None, int, tuple])
        Return:
            if original_e=None, then the graph is the whole original graph generated by
            generate_weighted_graph(), so just return the circuit transformed by it

            if original_e is a int, then the subgraph is generated by node(idx = original_e
            in whole graph), so return the it's idx mapped by node_to_qubit[], and the circuit

            if original_e is a tuple, then the subgraph is generated by edge(node idx = original_e
            in whole graph), so return the it's idx mapped by node_to_qubit[] as
            tuple(mapped node_id1, mapped node_id2), and the circuit
        """
        original_e, graph = element_graph
        node_to_qubit = defaultdict(int)
        node_list = list(graph.nodes)
        for i in range(len(node_list)):
            node_to_qubit[node_list[i]] = i

        circ = cirq.Circuit()
        ql = cirq.LineQubit.range(len(node_list))
        circ.append(cirq.H(ql[i]) for i in range(len(node_list)))

        gamma_list, beta_list = self._pargs[: self._p], self._pargs[self._p:]
        for k in range(self._p):
            for i in graph.nodes:
                u = node_to_qubit[i]
                circ.append(cirq.rz(2 * gamma_list * self._nodes_weight[i]).on(ql[u]))

            for edge in graph.edges:
                u, v = node_to_qubit[edge[0]], node_to_qubit[edge[1]]
                if u == v:
                    continue

                circ.append(cirq.CX(ql[u], ql[v]))
                circ.append(cirq.rz(2 * gamma_list * self._edges_weight[edge[0], edge[1]]).on(ql[v]))
                circ.append(cirq.CX(ql[u], ql[v]))

            for nd in graph.nodes:
                u = node_to_qubit[nd]
                circ.append(cirq.Moment(cirq.rx(2 * beta_list).on(ql[u])))

        qubits = cirq.LineQubit.range(len(node_list))
        qubit_map = dict(zip(qubits, range(len(node_list))))

        if isinstance(original_e, int):
            weight = self._nodes_weight[original_e]
            op = cirq.Z(qubits[node_to_qubit[original_e]])
        else:
            weight = self._edges_weight[original_e]
            op = cirq.Z(qubits[node_to_qubit[original_e[0]]]) * cirq.Z(qubits[node_to_qubit[original_e[1]]])

        state = cirq.final_state_vector(circ)
        exp_res = op.expectation_from_state_vector(state, qubit_map=qubit_map)

        return weight * exp_res.real

    def expectation_calculation(self):
        if self._is_parallel:
            return self.expectation_calculation_parallel()
        else:
            return self.expectation_calculation_serial()

    def expectation_calculation_serial(self):
        import os
        from multiprocessing import cpu_count

        cpu_num = cpu_count()
        os.environ['OMP_NUM_THREADS'] = str(cpu_num)
        os.environ['OPENBLAS_NUM_THREADS'] = str(cpu_num)
        os.environ['MKL_NUM_THREADS'] = str(cpu_num)
        os.environ['VECLIB_MAXIMUM_THREADS'] = str(cpu_num)
        os.environ['NUMEXPR_NUM_THREADS'] = str(cpu_num)

        res = 0
        for item in self._element_to_graph.items():
            res += self.get_expectation(item)

        print("Total expectation of original graph is: ", res)
        self._expectation_path.append(res)
        return res

    def expectation_calculation_parallel(self):
        cpu_num = 1
        os.environ['OMP_NUM_THREADS'] = str(cpu_num)
        os.environ['OPENBLAS_NUM_THREADS'] = str(cpu_num)
        os.environ['MKL_NUM_THREADS'] = str(cpu_num)
        os.environ['VECLIB_MAXIMUM_THREADS'] = str(cpu_num)
        os.environ['NUMEXPR_NUM_THREADS'] = str(cpu_num)

        circ_res = []
        pool = Pool(os.cpu_count())  # , maxtasksperchild=1
        circ_res.append(pool.map(self.get_expectation, list(self._element_to_graph.items()), chunksize=1))

        pool.terminate()  # pool.close()
        pool.join()

        res = sum(circ_res[0])
        print("Total expectation of original graph is: ", res)
        self._expectation_path.append(res)
        return res

    def visualization(self):
        plt.figure()
        plt.plot(range(1, len(self._expectation_path) + 1), self._expectation_path, "ob-", label="cirq")
        plt.ylabel('Expectation value')
        plt.xlabel('Number of iterations')
        plt.legend()
        plt.show()


# definite a Gate
# class Rx(cirq.Gate):
#     def __init__(self, theta):
#         super(Rx, self)
#         self.theta = theta
#
#     def _num_qubits_(self):
#         return 1
#
#     def _unitary_(self):
#         return np.array([
#             [np.cos(self.theta), np.sin(self.theta)],
#             [np.sin(self.theta), -np.cos(self.theta)]
#         ]) / np.sqrt(2)
#
#     def _circuit_diagram_info_(self, args):
#         return f"R({self.theta})"


# expectation calculate test
# define two qubits
# q0 = cirq.GridQubit(0,0)
# q1 = cirq.GridQubit(0,1)
#
# # make a PauliSum gate that will return [1] if the state is a bell state b00 (|00>)
# z0 = cirq.Z(q0)
# z1 = cirq.Z(q1)
# z00 = (((1+z0)/2)*((1+z1)/2) )
#
# # define three parameters, x will be varied - a,b are fixed
# phi = sp.Symbol('phi')
# alpha = sp.Symbol('alpha')
# beta = sp.Symbol('beta')
#
#
# circuit = cirq.Circuit([
#                 cirq.rx(phi)(q0),
#                 cirq.ry(-2*phi)(q1),
#                 cirq.H(q0),
#                 cirq.CNOT(q0,q1),
#                 cirq.rx(alpha)(q0),
#                 cirq.ry(beta)(q1),
#                 ])
# #fix two values of alpha and beta
# a = 1.8
# b = -3
#
# #loop over phi from -6 to 6
# x_values = np.arange(-6,6,0.05)
# y_expectations = []
#
# for j in x_values:
#     #resolve the circuit for different values of phi
#     resolver = cirq.ParamResolver({'alpha':a,'beta':b,'phi':j})
#
#     #calcuclate the expectation value
#     result = cirq.Simulator().simulate(cirq.resolve_parameters(circuit,resolver))
#     e = z00.expectation_from_state_vector(result.final_state_vector,{q0:0,q1:1})
#     y_expectations.append(e)
#
# plt.scatter(x_values,y_expectations,label=f'Expected, $\\alpha$={a}, $\\beta$={b}')
# plt.xlabel('$\phi$')
# plt.ylabel('Expectation')
# plt.legend()
# plt.show()


# another example of expectation calculate
# qubits = cirq.LineQubit.range(nqubits)
# # qubit order in the observables must match the qubit order in the circuit used to generate |a>
# qubit_map = dict(zip(qubits, range(nqubits)))
#
# for (i, j) in MyGraph.edges():
#   # make the Z_i*Z_j observable
#   ZiZj = cirq.Z(qubits[i]) * cirq.Z(qubits[j])
#   # compute desired expectation
#   expectation_ZiZj = ZiZj.expectation_from_state_vector(a, qubit_map=qubit_map)


# small circuit test
# import cirq
# # Pick a qubit.
# qubit = cirq.GridQubit(0, 0)
#
# # Create a circuit
# circuit = cirq.Circuit(
#     cirq.X(qubit) ** 0.5,  # Square root of NOT.
#     cirq.measure(qubit, key='m')  # Measurement.
# )
# print("Circuit:")
# print(circuit)
#
# # Simulate the circuit several times.
# simulator = cirq.Simulator()
# result = simulator.run(circuit, repetitions=20)
# print("Results:")
# print(result)