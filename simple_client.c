//
// Hello World client
// Connects REQ socket to tcp://localhost:5559
// Sends "Hello" to server, expects "World" back
//
#include "zhelpers.h"

int main (void)
{
    void *context = zmq_init (1);
    
    // Socket to talk to server
    void *requester = zmq_socket (context, ZMQ_DEALER);
    zmq_setsockopt(requester, ZMQ_IDENTITY, "test", 4);
    zmq_connect (requester, "ipc:///var/log/cluster/sockets/collrelay/receiver");
    
    int request_nbr;
    for (request_nbr = 0; request_nbr != 10; request_nbr++) {
        s_send (requester, "Hello");
        char *string = s_recv (requester);
        printf ("Received reply %d [%s]\n", request_nbr, string);
        free (string);
    }
    zmq_close (requester);
    zmq_term (context);
    return 0;
}
