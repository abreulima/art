Crie um cliente completo em **Python** usando **pyray (Raylib)**.

* Conectar via **UDP** em `192.168.1.81:5550`
* Enviar continuamente:

```json
{"type":"update","name":"player","image":"players/player.png","x":X,"y":Y}
```

* Receber:

```json
{"type":"world","players":[...]}
```

### Regras

* O mapa é sempre `map.png` (local) e deve ser carregado **uma única vez**
* Desenhar o mapa como fundo
* Desenhar todos os jogadores nas posições recebidas (usando suas imagens)

### Jogador local

* Movimento com **W, A, S, D**
* Atualizar `x` e `y` e enviar ao servidor

### Técnica

* Usar **thread separada** para receber dados UDP
* Loop principal: input + renderização

### Entrega

Código completo em **um único arquivo**, pronto para rodar
